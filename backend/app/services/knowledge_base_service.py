"""Chroma 向量数据库接入服务，支持父子分段检索。"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import shutil
import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Sequence

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
import numpy as np

from app.core.config import settings
from app.services.embeddings.qwen import QwenEmbeddings

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent


def _ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _resolve_path(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    parts = path.parts
    if parts and parts[0] == "backend":
        return PROJECT_ROOT / path
    return BACKEND_ROOT / path
    return path


class HashEmbeddings(Embeddings):
    """Deterministic local fallback so vector sync won't depend on external services."""

    def __init__(self, dim: int = 1024) -> None:
        self._dim = dim

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str | None) -> list[float]:
        content = (text or "").encode("utf-8", errors="ignore")
        digest = hashlib.sha256(content).digest()
        rng = np.random.default_rng(int.from_bytes(digest[:8], "big", signed=False))
        return rng.standard_normal(self._dim).tolist()


class ResilientEmbeddings(Embeddings):
    """Try the preferred provider first, then degrade to other providers or local hash."""

    def __init__(self, candidates: list[tuple[str, Embeddings]]) -> None:
        self._candidates = candidates
        self._active_index = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._call("embed_documents", texts)

    def embed_query(self, text: str) -> list[float]:
        return self._call("embed_query", text)

    def _call(self, method_name: str, payload):
        errors: list[str] = []
        for idx, (name, embedding) in enumerate(self._candidates):
            try:
                result = getattr(embedding, method_name)(payload)
                if idx != self._active_index:
                    logger.warning("Embedding provider switched from %s to %s", self._candidates[self._active_index][0], name)
                    self._active_index = idx
                return result
            except Exception as exc:  # pragma: no cover
                logger.warning("Embedding provider %s failed during %s: %s", name, method_name, exc)
                errors.append(f"{name}: {exc}")
        raise RuntimeError("All embedding providers failed: " + " | ".join(errors))


def _build_embeddings():
    qwen_model = settings.RAG_EMBED_MODEL or settings.EMBEDDING_MODEL
    candidates: list[tuple[str, Embeddings]] = []

    def _append_candidate(name: str, factory) -> None:
        try:
            candidates.append((name, factory()))
        except Exception as exc:  # pragma: no cover
            logger.warning("Embedding provider %s initialization failed: %s", name, exc)

    _append_candidate(
        "qwen",
        lambda: QwenEmbeddings(
            api_key=settings.QWEN_API_KEY,
            model=qwen_model,
            api_base=settings.QWEN_API_BASE,
        )
        if settings.QWEN_API_KEY
        else (_ for _ in ()).throw(ValueError("QWEN_API_KEY 未配置")),
    )

    candidates.append(("hash-fallback", HashEmbeddings()))
    return ResilientEmbeddings(candidates)


class KnowledgeBaseService:
    """封装 Chroma 向量库，父子分段通过 metadata 聚合。"""

    def __init__(self) -> None:
        persist_dir = _ensure_directory(_resolve_path(settings.CHROMA_PERSIST_DIR))

        self._embeddings = _build_embeddings()
        try:
            self._vectorstore = Chroma(
                collection_name=settings.CHROMA_COLLECTION_NAME,
                embedding_function=self._embeddings,
                persist_directory=str(persist_dir),
            )
        except KeyError as exc:  # 旧版元数据不兼容时重建
            logger.warning("Chroma 元数据损坏，尝试重建向量库: %s", exc)
            shutil.rmtree(persist_dir, ignore_errors=True)
            _ensure_directory(persist_dir)
            self._vectorstore = Chroma(
                collection_name=settings.CHROMA_COLLECTION_NAME,
                embedding_function=self._embeddings,
                persist_directory=str(persist_dir),
            )

        self._parent_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.PARENT_CHUNK_SIZE,
            chunk_overlap=settings.PARENT_CHUNK_OVERLAP,
        )
        self._child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHILD_CHUNK_SIZE,
            chunk_overlap=settings.CHILD_CHUNK_OVERLAP,
        )

    def _make_child_documents(self, document: Document) -> list[Document]:
        base_metadata = dict(document.metadata or {})
        base_metadata.setdefault("source", base_metadata.get("source", "知识库"))
        base_metadata.setdefault("question", base_metadata.get("question"))
        parent_seed = base_metadata.get("parent_id") or str(uuid.uuid4())

        parent_chunks = self._parent_splitter.split_text(document.page_content)
        if not parent_chunks:
            parent_chunks = [document.page_content]

        child_documents: list[Document] = []
        for parent_idx, parent_content in enumerate(parent_chunks):
            parent_id = f"{parent_seed}-{parent_idx}"
            parent_metadata = dict(base_metadata)
            parent_metadata["parent_id"] = parent_id
            parent_metadata["parent_content"] = parent_content

            parent_doc = Document(page_content=parent_content, metadata=parent_metadata)
            splits = self._child_splitter.split_documents([parent_doc])
            if not splits:
                fallback = Document(page_content=parent_content, metadata=dict(parent_metadata))
                fallback.metadata["chunk_id"] = f"{parent_id}-0"
                child_documents.append(fallback)
                continue
            for chunk_idx, child in enumerate(splits):
                child.metadata = dict(parent_metadata)
                child.metadata["chunk_id"] = f"{parent_id}-{chunk_idx}"
                child_documents.append(child)

        return child_documents

    def add_documents(self, documents: Sequence[Document]) -> None:
        if not documents:
            logger.info("知识库接收到空文档列表，跳过入库")
            return

        child_docs: list[Document] = []
        for document in documents:
            child_docs.extend(self._make_child_documents(document))

        if not child_docs:
            logger.warning("未生成任何子文档，确认原始数据是否为空")
            return

        self._vectorstore.add_documents(child_docs)
        # langchain-chroma 从 0.4 起默认使用持久化客户端，新增数据会自动落盘

    async def asearch(self, query: str, *, k: int | None = None) -> list[Document]:
        """检索并聚合父文档，默认返回配置的 Top-K。"""

        limit = k or settings.CHROMA_TOP_K
        # 多取一些子块，以便聚合后仍有足够父文档
        child_limit = max(limit * 3, limit)
        loop = asyncio.get_running_loop()
        child_docs: list[Document] = await loop.run_in_executor(
            None, self._vectorstore.similarity_search, query, child_limit
        )
        return self._aggregate_parent_documents(child_docs, limit)

    @staticmethod
    def _aggregate_parent_documents(child_docs: Sequence[Document], limit: int) -> list[Document]:
        parents: OrderedDict[str, Document] = OrderedDict()
        for child in child_docs:
            metadata = dict(child.metadata or {})
            parent_id = metadata.get("parent_id")
            if not parent_id:
                continue
            if parent_id in parents:
                continue

            parent_content = metadata.pop("parent_content", child.page_content)
            metadata.pop("chunk_id", None)
            parents[parent_id] = Document(page_content=parent_content, metadata=metadata)
            if len(parents) >= limit:
                break
        return list(parents.values())


knowledge_base_service = KnowledgeBaseService()


def get_knowledge_base_service() -> KnowledgeBaseService:
    return knowledge_base_service
