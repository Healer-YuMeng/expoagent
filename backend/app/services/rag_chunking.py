"""Shared parent-child chunking helpers for RAG ingestion and retrieval."""

from __future__ import annotations

import uuid
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import settings


def _build_parent_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.PARENT_CHUNK_SIZE,
        chunk_overlap=settings.PARENT_CHUNK_OVERLAP,
    )


def _build_child_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.CHILD_CHUNK_SIZE,
        chunk_overlap=settings.CHILD_CHUNK_OVERLAP,
    )


def build_parent_child_chunks(
    text: str,
    *,
    metadata: dict[str, Any] | None = None,
    parent_seed: str | None = None,
) -> list[dict[str, Any]]:
    """Split a document into parent chunks, then child chunks with retrieval metadata."""
    content = (text or "").strip()
    if not content:
        return []

    base_metadata = dict(metadata or {})
    seed = parent_seed or base_metadata.get("parent_id") or str(uuid.uuid4())

    parent_splitter = _build_parent_splitter()
    child_splitter = _build_child_splitter()

    parent_chunks = parent_splitter.split_text(content) or [content]
    child_chunks: list[dict[str, Any]] = []

    for parent_idx, parent_content in enumerate(parent_chunks):
        parent_id = f"{seed}-{parent_idx}"
        parent_metadata = dict(base_metadata)
        parent_metadata["parent_id"] = parent_id
        parent_metadata["parent_content"] = parent_content
        parent_metadata["parent_chunk_index"] = parent_idx

        child_texts = child_splitter.split_text(parent_content) or [parent_content]
        for child_idx, child_content in enumerate(child_texts):
            chunk_metadata = dict(parent_metadata)
            chunk_metadata["chunk_id"] = f"{parent_id}-{child_idx}"
            chunk_metadata["child_chunk_index"] = child_idx
            child_chunks.append(
                {
                    "content": child_content,
                    "metadata": chunk_metadata,
                }
            )

    return child_chunks


def ensure_parent_chunk_metadata(
    content: str,
    metadata: dict[str, Any] | None = None,
    *,
    parent_seed: str | None = None,
) -> dict[str, Any]:
    """Ensure manually managed chunks also have parent-child retrieval metadata."""
    base_metadata = dict(metadata or {})
    seed = parent_seed or base_metadata.get("parent_id") or str(uuid.uuid4())

    if base_metadata.get("parent_id"):
        parent_id = str(base_metadata["parent_id"])
    else:
        parent_id = f"{seed}-0"
    child_idx = int(base_metadata.get("child_chunk_index", 0) or 0)

    base_metadata["parent_id"] = parent_id
    base_metadata["parent_content"] = content
    base_metadata["parent_chunk_index"] = int(base_metadata.get("parent_chunk_index", 0) or 0)
    base_metadata["child_chunk_index"] = child_idx
    base_metadata["chunk_id"] = str(base_metadata.get("chunk_id") or f"{parent_id}-{child_idx}")
    return base_metadata
