"""Chroma vector store for RAG chunks."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, Optional, Any

from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.services.knowledge_base_service import _build_embeddings


def _normalize_metadata_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _normalize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {key: _normalize_metadata_value(value) for key, value in metadata.items()}


def _slugify_for_path(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value or "").strip("-._")
    return slug or "default"


def build_rag_vector_persist_dir(base_dir: Path, school_key: str | None, embed_model: str) -> Path:
    model_slug = _slugify_for_path(embed_model)
    if school_key:
        return base_dir / school_key / model_slug
    return base_dir / "_global" / model_slug


def build_rag_vector_collection_name(base_name: str, embed_model: str) -> str:
    return f"{base_name}_{_slugify_for_path(embed_model)}"


class RagVectorStore:
    def __init__(self, persist_dir: Path, collection: str, embed_model: str) -> None:
        self._persist_dir = persist_dir
        self._collection = collection
        self._embed_model = embed_model
        # 复用现有 embedding 构造逻辑，支持 openai/ollama/qwen 等 provider
        self._embeddings = _build_embeddings()
        self._init_store()

    def _init_store(self) -> None:
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        try:
            (self._persist_dir / ".touch").touch(exist_ok=True)
        except Exception:
            pass
        self._store = Chroma(
            collection_name=self._collection,
            persist_directory=str(self._persist_dir),
            embedding_function=self._embeddings,
        )

    def add_chunks(self, chunks: Iterable[dict]) -> None:
        docs: list[Document] = []
        ids: list[str] = []
        for chunk in chunks:
            chunk_id = chunk.get("id")
            if not chunk_id:
                continue
            ids.append(chunk_id)
            meta = _normalize_metadata(dict(chunk.get("metadata") or {}))
            meta.setdefault("doc_id", chunk.get("doc_id"))
            meta.setdefault("doc_name", chunk.get("doc_name"))
            meta.setdefault("chunk_index", chunk.get("chunk_index"))
            meta.setdefault("id", chunk_id)
            docs.append(Document(page_content=chunk.get("content", ""), metadata=meta))
        if docs:
            self._store.add_documents(documents=docs, ids=ids)

    def delete(self, ids: list[str]) -> None:
        if ids:
            self._store.delete(ids=ids)

    def update(self, chunk: dict) -> None:
        cid = chunk.get("id")
        if not cid:
            return
        self.delete([cid])
        self.add_chunks([chunk])

    def replace_all(self, chunks: Iterable[dict]) -> None:
        existing = self._store.get()
        existing_ids = existing.get("ids") or []
        if existing_ids:
            self._store.delete(ids=existing_ids)
        self.add_chunks(chunks)

    def query(self, query: str, k: int = 5) -> list[dict]:
        docs_with_scores = self._store.similarity_search_with_score(query, k=k)
        results: list[dict[str, Any]] = []
        for doc, dist in docs_with_scores:
            meta = dict(doc.metadata or {})
            score = 1 / (1 + dist) if dist is not None else 0.0
            cid = meta.get("id")
            results.append({
                "id": cid,
                "doc_id": meta.get("doc_id"),
                "doc_name": meta.get("doc_name"),
                "content": doc.page_content,
                "metadata": meta,
                "score": score,
            })
        return results
