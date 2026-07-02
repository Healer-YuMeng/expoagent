from __future__ import annotations

from typing import Any, Iterable, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from app.db import PostgresCompatDatabase


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _extract_candidate_chunk_ids(items: Sequence[dict[str, Any]]) -> list[str]:
    chunk_ids: list[str] = []
    seen: set[str] = set()
    for item in items:
        matched_chunk_ids = item.get("matched_chunk_ids")
        if isinstance(matched_chunk_ids, list) and matched_chunk_ids:
            raw_ids: Iterable[Any] = matched_chunk_ids
        else:
            raw_ids = [item.get("id")]
        for raw_id in raw_ids:
            chunk_id = _normalize_text(raw_id)
            if not chunk_id or chunk_id in seen:
                continue
            seen.add(chunk_id)
            chunk_ids.append(chunk_id)
    return chunk_ids


async def filter_live_rag_results(
    db: PostgresCompatDatabase,
    *,
    school_id: str | None,
    items: Sequence[dict[str, Any]],
    knowledge_base_ids: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    if not items:
        return []

    candidate_chunk_ids = _extract_candidate_chunk_ids(items)
    if not candidate_chunk_ids:
        return []

    chunk_query: dict[str, Any] = {"_id": {"$in": candidate_chunk_ids}}
    normalized_school_id = _normalize_text(school_id)
    if normalized_school_id:
        chunk_query["school_id"] = normalized_school_id

    live_chunk_map: dict[str, dict[str, Any]] = {}
    chunk_cursor = db["rag_chunks"].find(chunk_query)
    async for chunk in chunk_cursor:
        chunk_id = _normalize_text(chunk.get("_id"))
        if not chunk_id:
            continue
        live_chunk_map[chunk_id] = chunk

    if not live_chunk_map:
        return []

    allowed_knowledge_base_ids = {
        _normalize_text(item)
        for item in (knowledge_base_ids or [])
        if _normalize_text(item)
    }

    doc_ids = {
        _normalize_text(chunk.get("doc_id"))
        for chunk in live_chunk_map.values()
        if _normalize_text(chunk.get("doc_id"))
    }
    live_doc_ids: set[str] = set()
    if doc_ids:
        doc_query: dict[str, Any] = {"_id": {"$in": list(doc_ids)}}
        if normalized_school_id:
            doc_query["school_id"] = normalized_school_id
        doc_cursor = db["rag_documents"].find(doc_query)
        async for doc in doc_cursor:
            doc_id = _normalize_text(doc.get("_id"))
            if doc_id:
                live_doc_ids.add(doc_id)

    filtered_items: list[dict[str, Any]] = []
    for item in items:
        matched_chunk_ids = item.get("matched_chunk_ids")
        if isinstance(matched_chunk_ids, list) and matched_chunk_ids:
            source_chunk_ids = [_normalize_text(chunk_id) for chunk_id in matched_chunk_ids]
        else:
            source_chunk_ids = [_normalize_text(item.get("id"))]

        live_chunk_ids: list[str] = []
        for chunk_id in source_chunk_ids:
            if not chunk_id:
                continue
            chunk = live_chunk_map.get(chunk_id)
            if not chunk:
                continue
            chunk_doc_id = _normalize_text(chunk.get("doc_id"))
            if chunk_doc_id and live_doc_ids and chunk_doc_id not in live_doc_ids:
                continue
            chunk_knowledge_base_id = _normalize_text(chunk.get("knowledge_base_id"))
            if allowed_knowledge_base_ids and chunk_knowledge_base_id not in allowed_knowledge_base_ids:
                continue
            live_chunk_ids.append(chunk_id)

        if not live_chunk_ids:
            continue

        primary_chunk = live_chunk_map[live_chunk_ids[0]]
        next_item = dict(item)
        if isinstance(matched_chunk_ids, list):
            next_item["matched_chunk_ids"] = live_chunk_ids
        next_item["doc_id"] = _normalize_text(
            next_item.get("doc_id")
            or primary_chunk.get("doc_id")
            or (primary_chunk.get("metadata") or {}).get("doc_id")
        ) or None

        metadata = dict(next_item.get("metadata") or {})
        if primary_chunk.get("knowledge_base_id") is not None:
            metadata["knowledge_base_id"] = primary_chunk.get("knowledge_base_id")
        if primary_chunk.get("doc_id") is not None:
            metadata["doc_id"] = primary_chunk.get("doc_id")
        next_item["metadata"] = metadata
        filtered_items.append(next_item)

    return filtered_items
