from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Query, status
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.core.dependencies import get_current_teacher
from app.db import PostgresCompatDatabase, get_database
from app.models.user import UserSchema
from app.services.doc_ingest import DocIngestor
from app.services.storage import StorageClient, StorageConfig
from app.services.rag_store import RagStore
from app.models.rag import DocRecord, ChunkRecord, KnowledgeBaseRecord
from app.services.hybrid_retriever import HybridRetriever
from app.services.rag_vector_store import (
    RagVectorStore,
    build_rag_vector_collection_name,
    build_rag_vector_persist_dir,
)
from app.services.url_ingest import UrlIngestor
from app.services import rag_search
from app.services.rag_chunking import ensure_parent_chunk_metadata

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/docs", tags=["知识库文档"])


async def _resolve_teacher_school(
    db: PostgresCompatDatabase,
    user: UserSchema,
    requested_school_id: Optional[str] = None,
) -> str:
    if user.role == "admin":
        if not user.school_id:
            raise HTTPException(status_code=400, detail="管理员未绑定学校，无法操作知识库")
        return user.school_id
    if user.role == "sales":
        if user.school_id:
            return user.school_id
        if not user.admin_id:
            raise HTTPException(status_code=400, detail="销售未绑定普通管理员，无法操作知识库")
        admin_doc = await db.users.find_one({"_id": user.admin_id}, {"school_id": 1})
        school_id = str(admin_doc.get("school_id") or "").strip() if admin_doc else ""
        if not school_id:
            raise HTTPException(status_code=400, detail="销售所属学校未配置，无法操作知识库")
        return school_id
    school_id = (requested_school_id or "").strip()
    if not school_id:
        raise HTTPException(status_code=400, detail="school_id 不能为空")
    return school_id


def _get_storage() -> StorageClient:
    cfg = StorageConfig(
        endpoint=settings.RAG_MINIO_ENDPOINT or "",
        access_key=settings.RAG_MINIO_ACCESS_KEY or "",
        secret_key=settings.RAG_MINIO_SECRET_KEY or "",
        bucket=settings.RAG_BUCKET,
        secure=bool(settings.RAG_MINIO_SECURE),
        base_dir=Path(settings.RAG_TMP_DIR),
    )
    return StorageClient(cfg)


def _get_retriever(school_id: str) -> HybridRetriever:
    base = Path(settings.RAG_BM25_CACHE)
    cache = base.with_name(f"{base.stem}_{school_id}{base.suffix}")
    return HybridRetriever(cache)


def _get_vector_store(school_id: str) -> RagVectorStore:
    return RagVectorStore(
        persist_dir=build_rag_vector_persist_dir(Path(settings.RAG_CHROMA_DIR), school_id, settings.RAG_EMBED_MODEL),
        collection=build_rag_vector_collection_name("fy_rag_chunks", settings.RAG_EMBED_MODEL),
        embed_model=settings.RAG_EMBED_MODEL,
    )


def _get_url_ingestor() -> UrlIngestor:
    return UrlIngestor()


async def _require_knowledge_base(
    store: RagStore,
    *,
    school_id: str,
    knowledge_base_id: str,
) -> dict:
    knowledge_base = await store.get_knowledge_base(knowledge_base_id)
    if not knowledge_base:
        raise HTTPException(status_code=404, detail="知识库不存在")
    if knowledge_base.get("school_id") != school_id:
        raise HTTPException(status_code=403, detail="无权访问其他学校知识库")
    return knowledge_base


def _chunk_to_vector_payload(
    *,
    chunk_id: str,
    doc_id: str | None,
    content: str,
    metadata: dict | None,
) -> dict:
    meta = dict(metadata or {})
    return {
        "id": chunk_id,
        "doc_id": doc_id,
        "doc_name": meta.get("doc_name"),
        "content": content,
        "metadata": meta,
    }


async def _run_vector_operation(school_id: str, action: str, operator) -> str | None:
    """Run vector writes as best-effort so doc management can still succeed."""
    try:
        operator()
        return None
    except Exception as exc:  # pragma: no cover
        logger.exception("RAG vector store %s failed for school %s: %s", action, school_id, exc)
        return "向量库同步失败，当前数据已保存，可继续使用 BM25 检索。请检查 embedding/Chroma 配置。"


async def _list_school_chunk_payloads(db: PostgresCompatDatabase, school_id: str) -> list[dict]:
    items: list[dict] = []
    cursor = db["rag_chunks"].find({"school_id": school_id}).sort("created_at", 1)
    async for chunk_doc in cursor:
        chunk_id = str(chunk_doc.get("_id"))
        metadata = dict(chunk_doc.get("metadata") or {})
        metadata.setdefault("knowledge_base_id", chunk_doc.get("knowledge_base_id"))
        items.append(
            _chunk_to_vector_payload(
                chunk_id=chunk_id,
                doc_id=chunk_doc.get("doc_id"),
                content=chunk_doc.get("content", ""),
                metadata=metadata,
            )
        )
    return items


async def _rebuild_school_indexes(db: PostgresCompatDatabase, school_id: str) -> str | None:
    items = await _list_school_chunk_payloads(db, school_id)
    retriever = _get_retriever(school_id)
    retriever.replace_all(
        [
            {"id": item["id"], "content": item["content"], **(item.get("metadata") or {})}
            for item in items
        ]
    )
    return await _run_vector_operation(
        school_id,
        "replace_all_chunks",
        lambda: _get_vector_store(school_id).replace_all(items),
    )


async def _ensure_retriever_ready(retriever: HybridRetriever, db: PostgresCompatDatabase, school_id: str) -> None:
    # 若缓存为空，尝试从 DB 预热 BM25
    if getattr(retriever, "_bm25_meta", []):
        return
    items: list[dict] = []
    cursor = db["rag_chunks"].find({"school_id": school_id})
    async for c in cursor:
        cid = str(c.get("_id"))
        items.append({"id": cid, "content": c.get("content", ""), **(c.get("metadata") or {})})
    if items:
        retriever.add_chunks(items)


@router.get("/knowledge-bases", summary="知识库列表")
async def list_knowledge_bases(
    school_id: Optional[str] = Query(default=None),
    db: PostgresCompatDatabase = Depends(get_database),
    current_teacher: UserSchema = Depends(get_current_teacher),
):
    school_id = await _resolve_teacher_school(db, current_teacher, school_id)
    store = RagStore(db)
    knowledge_bases = await store.list_knowledge_bases(school_id=school_id)
    doc_counts = await store.count_docs_by_knowledge_base(school_id=school_id)
    return {
        "items": [
            {
                **item,
                "doc_count": doc_counts.get(str(item.get("id")), 0),
            }
            for item in knowledge_bases
        ]
    }


@router.post("/knowledge-bases", summary="新建知识库")
async def create_knowledge_base(
    payload: dict,
    db: PostgresCompatDatabase = Depends(get_database),
    current_teacher: UserSchema = Depends(get_current_teacher),
):
    school_id = await _resolve_teacher_school(db, current_teacher, payload.get("school_id"))
    name = str(payload.get("name") or "").strip()
    description = str(payload.get("description") or "").strip() or None
    if not name:
        raise HTTPException(status_code=400, detail="知识库名称不能为空")
    store = RagStore(db)
    existing = await store.get_knowledge_base_by_name(school_id=school_id, name=name)
    if existing:
        raise HTTPException(status_code=409, detail="知识库名称已存在")

    knowledge_base = KnowledgeBaseRecord(
        id=str(uuid.uuid4()),
        name=name,
        school_id=school_id,
        admin_id=current_teacher.id,
        description=description,
    )
    await store.create_knowledge_base(knowledge_base)
    return {
        "id": knowledge_base.id,
        "name": knowledge_base.name,
        "description": knowledge_base.description,
        "school_id": knowledge_base.school_id,
        "doc_count": 0,
    }


@router.post("", summary="上传文档")
async def upload_doc(
    use_async: bool = Query(True, description="是否异步处理"),
    knowledge_base_id: str = Form(...),
    file: UploadFile = File(...),
    current_teacher: UserSchema = Depends(get_current_teacher),
    db: PostgresCompatDatabase = Depends(get_database),
):
    school_id = await _resolve_teacher_school(db, current_teacher)
    # 读取文件
    content = await file.read()
    storage = _get_storage()
    ingestor = DocIngestor(storage, Path(settings.RAG_TMP_DIR))
    store = RagStore(db)
    knowledge_base = await _require_knowledge_base(
        store,
        school_id=school_id,
        knowledge_base_id=knowledge_base_id,
    )

    try:
        meta, chunks = ingestor.ingest(
            filename=file.filename or "upload",
            content=content,
            content_type=file.content_type,
            school_id=school_id,
            admin_id=current_teacher.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:  # pragma: no cover
        logger.error("Doc ingest failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="文档处理失败")

    doc_record = DocRecord(
        id=meta.doc_id,
        name=meta.name,
        object_name=meta.object_name,
        size=meta.size,
        knowledge_base_id=knowledge_base["id"],
        status=meta.status,
        chunk_count=meta.chunks,
        school_id=school_id,
        admin_id=current_teacher.id,
    )
    await store.save_doc(doc_record)

    chunk_records = []
    for c in chunks:
        meta_chunk = (c.get("metadata") or {}).copy()
        meta_chunk.setdefault("knowledge_base_id", knowledge_base["id"])
        meta_chunk.setdefault("knowledge_base_name", knowledge_base["name"])
        meta_chunk.setdefault("school_id", school_id)
        meta_chunk.setdefault("admin_id", current_teacher.id)
        chunk_records.append(
            ChunkRecord(
                id=str(uuid.uuid4()),
                doc_id=meta.doc_id,
                knowledge_base_id=knowledge_base["id"],
                school_id=school_id,
                admin_id=current_teacher.id,
                content=c.get("content", ""),
                metadata=meta_chunk,
            )
        )
    await store.add_chunks(chunk_records)

    retriever = _get_retriever(school_id)
    retriever.add_chunks([
        {"id": cr.id, "content": cr.content, **cr.metadata}
        for cr in chunk_records
    ])
    warning = await _run_vector_operation(
        school_id,
        "add_chunks",
        lambda: _get_vector_store(school_id).add_chunks([
            _chunk_to_vector_payload(
                chunk_id=cr.id,
                doc_id=meta.doc_id,
                content=cr.content,
                metadata=cr.metadata,
            )
            for cr in chunk_records
        ]),
    )

    response = {
        "id": meta.doc_id,
        "name": meta.name,
        "knowledge_base_id": knowledge_base["id"],
        "status": meta.status,
        "chunk_count": meta.chunks,
    }
    if warning:
        response["warning"] = warning
    return response


@router.get("", summary="文档列表")
async def list_docs(
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    knowledge_base_id: Optional[str] = Query(None),
    db: PostgresCompatDatabase = Depends(get_database),
    current_teacher: UserSchema = Depends(get_current_teacher),
):
    school_id = await _resolve_teacher_school(db, current_teacher)
    store = RagStore(db)
    docs = await store.list_docs(
        status=status_filter,
        search=search,
        school_id=school_id,
        knowledge_base_id=knowledge_base_id,
    )
    count_filter = {"school_id": school_id}
    if status_filter:
        count_filter["status"] = status_filter
    if knowledge_base_id:
        count_filter["knowledge_base_id"] = knowledge_base_id
    total = await db["rag_documents"].count_documents(count_filter)
    return {"items": docs, "total": total}


@router.get("/{doc_id}", summary="文档详情")
async def get_doc_detail(
    doc_id: str,
    db: PostgresCompatDatabase = Depends(get_database),
    current_teacher: UserSchema = Depends(get_current_teacher),
):
    school_id = await _resolve_teacher_school(db, current_teacher)
    store = RagStore(db)
    doc = await store.get_doc(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    if doc.get("school_id") and doc["school_id"] != school_id:
        raise HTTPException(status_code=403, detail="无权访问其他学校文档")
    return doc


@router.delete("/{doc_id}", summary="删除文档")
async def delete_doc(
    doc_id: str,
    db: PostgresCompatDatabase = Depends(get_database),
    current_teacher: UserSchema = Depends(get_current_teacher),
):
    school_id = await _resolve_teacher_school(db, current_teacher)
    store = RagStore(db)
    doc = await store.get_doc(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    if doc.get("school_id") and doc["school_id"] != school_id:
        raise HTTPException(status_code=403, detail="无权访问其他学校文档")

    # 删除存储对象
    obj_name = doc.get("object_name")
    if obj_name:
        storage = _get_storage()
        storage.delete(obj_name)

    delete_stats = await store.delete_doc(doc_id)
    logger.info(
        "删除知识库文档 %s 成功: doc_rows=%s, chunk_rows=%s",
        doc_id,
        delete_stats.get("deleted_doc_rows", 0),
        delete_stats.get("deleted_chunk_rows", 0),
    )
    warning = await _rebuild_school_indexes(db, school_id)
    response = {
        "message": "删除成功",
        "deleted_chunk_count": delete_stats.get("deleted_chunks", 0),
    }
    if warning:
        response["warning"] = warning
    return response


@router.get("/{doc_id}/chunks", summary="获取文档分块")
async def list_doc_chunks(
    doc_id: str,
    db: PostgresCompatDatabase = Depends(get_database),
    current_teacher: UserSchema = Depends(get_current_teacher),
):
    school_id = await _resolve_teacher_school(db, current_teacher)
    store = RagStore(db)
    doc = await store.get_doc(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    if doc.get("school_id") and doc["school_id"] != school_id:
        raise HTTPException(status_code=403, detail="无权访问其他学校文档")
    chunks = await store.list_chunks(doc_id)
    return {"items": chunks}


@router.post("/{doc_id}/chunks", summary="新增分块")
async def add_doc_chunk(
    doc_id: str,
    payload: dict,
    db: PostgresCompatDatabase = Depends(get_database),
    current_teacher: UserSchema = Depends(get_current_teacher),
):
    school_id = await _resolve_teacher_school(db, current_teacher)
    content = payload.get("content")
    if not content:
        raise HTTPException(status_code=400, detail="content 不能为空")
    metadata = payload.get("metadata") or {}
    metadata.setdefault("school_id", school_id)
    metadata.setdefault("admin_id", current_teacher.id)
    chunk = ChunkRecord(
        id=str(uuid.uuid4()),
        doc_id=doc_id,
        knowledge_base_id=None,
        school_id=school_id,
        admin_id=current_teacher.id,
        content=content,
        metadata={},
    )
    store = RagStore(db)
    doc = await store.get_doc(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    if doc.get("school_id") and doc["school_id"] != school_id:
        raise HTTPException(status_code=403, detail="无权访问其他学校文档")
    metadata.setdefault("knowledge_base_id", doc.get("knowledge_base_id"))
    metadata = ensure_parent_chunk_metadata(content, metadata)
    chunk.knowledge_base_id = doc.get("knowledge_base_id")
    chunk.metadata = metadata
    await store.add_chunks([chunk])
    retriever = _get_retriever(school_id)
    retriever.add_chunks([{"id": chunk.id, "content": chunk.content, **chunk.metadata}])
    warning = await _run_vector_operation(
        school_id,
        "add_chunk",
        lambda: _get_vector_store(school_id).add_chunks([
            _chunk_to_vector_payload(
                chunk_id=chunk.id,
                doc_id=doc_id,
                content=chunk.content,
                metadata=chunk.metadata,
            )
        ]),
    )
    await store.update_doc(doc_id, chunk_count=await store.count_chunks(doc_id))
    response = {"id": chunk.id}
    if warning:
        response["warning"] = warning
    return response


@router.post("/url", summary="从 URL 导入文档")
async def upload_url(
    payload: dict,
    db: PostgresCompatDatabase = Depends(get_database),
    current_teacher: UserSchema = Depends(get_current_teacher),
):
    school_id = await _resolve_teacher_school(db, current_teacher, payload.get("school_id"))
    url = (payload.get("url") or "").strip()
    knowledge_base_id = str(payload.get("knowledge_base_id") or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="url 不能为空")
    if not knowledge_base_id:
        raise HTTPException(status_code=400, detail="knowledge_base_id 不能为空")
    ingestor = _get_url_ingestor()
    store = RagStore(db)
    knowledge_base = await _require_knowledge_base(
        store,
        school_id=school_id,
        knowledge_base_id=knowledge_base_id,
    )
    try:
        meta, chunks = await ingestor.ingest(url)
    except Exception as exc:
        logger.error("URL ingest failed: %s", exc)
        raise HTTPException(status_code=500, detail="URL 处理失败") from exc

    doc_record = DocRecord(
        id=meta.doc_id,
        name=meta.name,
        object_name=meta.source_url,
        size=len(url.encode("utf-8")),
        knowledge_base_id=knowledge_base["id"],
        status=meta.status,
        chunk_count=meta.chunk_count,
        school_id=school_id,
        admin_id=current_teacher.id,
    )
    await store.save_doc(doc_record)

    chunk_records = []
    for c in chunks:
        meta_chunk = (c.get("metadata") or {}).copy()
        meta_chunk.setdefault("knowledge_base_id", knowledge_base["id"])
        meta_chunk.setdefault("knowledge_base_name", knowledge_base["name"])
        meta_chunk.setdefault("school_id", school_id)
        meta_chunk.setdefault("admin_id", current_teacher.id)
        chunk_records.append(
            ChunkRecord(
                id=str(uuid.uuid4()),
                doc_id=meta.doc_id,
                knowledge_base_id=knowledge_base["id"],
                school_id=school_id,
                admin_id=current_teacher.id,
                content=c.get("content", ""),
                metadata=meta_chunk,
            )
        )
    await store.add_chunks(chunk_records)

    retriever = _get_retriever(school_id)
    retriever.add_chunks([
        {"id": cr.id, "content": cr.content, **cr.metadata}
        for cr in chunk_records
    ])
    warning = await _run_vector_operation(
        school_id,
        "add_url_chunks",
        lambda: _get_vector_store(school_id).add_chunks([
            _chunk_to_vector_payload(
                chunk_id=cr.id,
                doc_id=meta.doc_id,
                content=cr.content,
                metadata=cr.metadata,
            )
            for cr in chunk_records
        ]),
    )

    response = {
        "id": meta.doc_id,
        "name": meta.name,
        "knowledge_base_id": knowledge_base["id"],
        "status": meta.status,
        "chunk_count": meta.chunk_count,
    }
    if warning:
        response["warning"] = warning
    return response


@router.patch("/chunks/{chunk_id}", summary="更新分块")
async def update_chunk(
    chunk_id: str,
    payload: dict,
    db: PostgresCompatDatabase = Depends(get_database),
    current_teacher: UserSchema = Depends(get_current_teacher),
):
    school_id = await _resolve_teacher_school(db, current_teacher)
    content = payload.get("content")
    metadata = payload.get("metadata")
    store = RagStore(db)
    chunk_doc = await store.get_chunk(chunk_id)
    if not chunk_doc:
        raise HTTPException(status_code=404, detail="分块不存在")
    meta = chunk_doc.get("metadata") or {}
    if meta.get("school_id") and meta["school_id"] != school_id:
        raise HTTPException(status_code=403, detail="无权访问其他学校分块")
    next_content = content if content is not None else chunk_doc.get("content", "")
    next_metadata = dict(meta)
    if metadata is not None:
        next_metadata.update(metadata)
    next_metadata.setdefault("school_id", meta.get("school_id") or school_id)
    next_metadata.setdefault("admin_id", meta.get("admin_id") or current_teacher.id)
    next_metadata.setdefault("knowledge_base_id", meta.get("knowledge_base_id") or chunk_doc.get("knowledge_base_id"))
    next_metadata = ensure_parent_chunk_metadata(next_content, next_metadata)
    ok = await store.update_chunk(
        chunk_id,
        content=content,
        metadata=next_metadata if (content is not None or metadata is not None) else None,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="分块不存在")
    retriever = _get_retriever(school_id)
    warning = None
    chunk_doc = await store.get_chunk(chunk_id)
    if chunk_doc:
        retriever.update_chunk({"id": chunk_id, "content": chunk_doc.get("content", ""), **(chunk_doc.get("metadata") or {})})
        warning = await _run_vector_operation(
            school_id,
            "update_chunk",
            lambda: _get_vector_store(school_id).update(
                _chunk_to_vector_payload(
                    chunk_id=chunk_id,
                    doc_id=chunk_doc.get("doc_id"),
                    content=chunk_doc.get("content", ""),
                    metadata=chunk_doc.get("metadata") or {},
                )
            ),
        )
    response = {"message": "更新成功"}
    if warning:
        response["warning"] = warning
    return response


@router.delete("/chunks/{chunk_id}", summary="删除分块")
async def delete_chunk(
    chunk_id: str,
    db: PostgresCompatDatabase = Depends(get_database),
    current_teacher: UserSchema = Depends(get_current_teacher),
):
    school_id = await _resolve_teacher_school(db, current_teacher)
    store = RagStore(db)
    chunk_doc = await store.get_chunk(chunk_id)
    if not chunk_doc:
        raise HTTPException(status_code=404, detail="分块不存在")
    meta = chunk_doc.get("metadata") or {}
    if meta.get("school_id") and meta["school_id"] != school_id:
        raise HTTPException(status_code=403, detail="无权访问其他学校分块")
    ok = await store.delete_chunk(chunk_id)
    if not ok:
        raise HTTPException(status_code=404, detail="分块不存在")
    warning = await _rebuild_school_indexes(db, school_id)
    response = {"message": "删除成功"}
    if warning:
        response["warning"] = warning
    return response


@router.post("/query", summary="查询知识库分块")
async def query_docs(
    payload: dict,
    db: PostgresCompatDatabase = Depends(get_database),
    current_teacher: UserSchema = Depends(get_current_teacher),
):
    school_id = await _resolve_teacher_school(db, current_teacher, payload.get("school_id"))
    query = (payload.get("query") or "").strip()
    knowledge_base_id = str(payload.get("knowledge_base_id") or "").strip() or None
    if not query:
        raise HTTPException(status_code=400, detail="query 不能为空")
    try:
        top_k = int(payload.get("top_k", 5))
    except Exception:
        top_k = 5
    top_k = max(1, min(top_k, 20))

    store = RagStore(db)
    if knowledge_base_id:
        await _require_knowledge_base(store, school_id=school_id, knowledge_base_id=knowledge_base_id)

    retriever = _get_retriever(school_id)
    await _ensure_retriever_ready(retriever, db, school_id)
    results = rag_search.search(
        query,
        top_k=max(top_k * 4, top_k),
        vector_weight=0.7,
        bm25_weight=0.3,
        school_key=school_id,
        aggregate_parents=False,
    )
    doc_ids: set[str] = set()
    for item in results:
        doc_id = str(item.get("doc_id") or (item.get("metadata") or {}).get("doc_id") or "")
        if doc_id:
            doc_ids.add(doc_id)

    doc_name_by_id: dict[str, str] = {}
    if doc_ids:
        doc_cursor = db["rag_documents"].find({"_id": {"$in": list(doc_ids)}})
        async for doc in doc_cursor:
            doc_name_by_id[str(doc.get("_id"))] = str(doc.get("name") or "")

    enriched_results = []
    for item in results:
        metadata = dict(item.get("metadata") or {})
        item_knowledge_base_id = str(
            item.get("knowledge_base_id")
            or metadata.get("knowledge_base_id")
            or ""
        )
        if knowledge_base_id and item_knowledge_base_id != knowledge_base_id:
            continue
        doc_id = str(item.get("doc_id") or metadata.get("doc_id") or "")
        doc_name = (
            item.get("doc_name")
            or metadata.get("doc_name")
            or doc_name_by_id.get(doc_id)
            or ""
        )
        enriched_results.append({
            **item,
            "doc_id": doc_id or None,
            "doc_name": doc_name,
            "knowledge_base_id": item_knowledge_base_id or None,
            "metadata": metadata,
        })
        if len(enriched_results) >= top_k:
            break

    return {"items": enriched_results}
