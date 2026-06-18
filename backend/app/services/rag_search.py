"""Hybrid search combining vector store and BM25 cache."""

from __future__ import annotations

import logging
import re
from collections import OrderedDict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services.hybrid_retriever import HybridRetriever
from app.services.rag_vector_store import (
    RagVectorStore,
    build_rag_vector_collection_name,
    build_rag_vector_persist_dir,
)

logger = logging.getLogger(__name__)
_RESULT_META_RESERVED_KEYS = {"id", "content", "score", "doc_id", "doc_name", "metadata"}
_LOOKUP_TEXT_KEYS = ("doc_name", "source", "object_name", "question")
_DOC_VERSION_RE = re.compile(r"v\d+(?:\.\d+)*", re.IGNORECASE)
_NON_LOOKUP_CHAR_RE = re.compile(r"[^0-9a-z\u4e00-\u9fff]+", re.IGNORECASE)


def _normalize_lookup_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    if not text:
        return ""
    text = re.sub(r"\.(pdf|docx|pptx|xlsx|md|txt|jpg|jpeg|png)$", "", text, flags=re.IGNORECASE)
    text = _DOC_VERSION_RE.sub("", text)
    return _NON_LOOKUP_CHAR_RE.sub("", text)


def _char_overlap_ratio(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    left_chars = {char for char in left if char.strip()}
    if not left_chars:
        return 0.0
    overlap = sum(1 for char in left_chars if char in right)
    return overlap / len(left_chars)


def _query_match_boost(query: str, item: dict[str, Any]) -> float:
    query_norm = _normalize_lookup_text(query)
    if len(query_norm) < 4:
        return 0.0

    metadata = _result_metadata(item)
    candidates = [
        item.get("doc_name"),
        *(metadata.get(key) for key in _LOOKUP_TEXT_KEYS),
    ]

    best = 0.0
    for candidate in candidates:
        candidate_norm = _normalize_lookup_text(candidate)
        if not candidate_norm:
            continue

        if query_norm == candidate_norm:
            best = max(best, 1.5)
            continue

        if query_norm in candidate_norm or candidate_norm in query_norm:
            best = max(best, 1.1)

        ratio = SequenceMatcher(None, query_norm, candidate_norm).ratio()
        overlap = _char_overlap_ratio(query_norm, candidate_norm)
        if ratio >= 0.82 or overlap >= 0.9:
            best = max(best, 0.95)
        elif ratio >= 0.70 or overlap >= 0.78:
            best = max(best, 0.72)
        elif ratio >= 0.58 or overlap >= 0.66:
            best = max(best, 0.42)

    content_norm = _normalize_lookup_text(item.get("content", ""))
    if content_norm and query_norm in content_norm:
        best = max(best, 0.35)

    return best


def _result_metadata(item: dict[str, Any]) -> dict[str, Any]:
    nested_metadata = item.get("metadata")
    if isinstance(nested_metadata, dict) and nested_metadata:
        return dict(nested_metadata)
    return {
        key: value
        for key, value in item.items()
        if key not in _RESULT_META_RESERVED_KEYS
    }


def _get_retriever(school_key: str | None = None) -> HybridRetriever:
    base = Path(settings.RAG_BM25_CACHE)
    if school_key:
        base = base.with_name(f"{base.stem}_{school_key}{base.suffix}")
    return HybridRetriever(base)


def _get_vector_store(school_key: str | None = None) -> RagVectorStore:
    return RagVectorStore(
        persist_dir=build_rag_vector_persist_dir(Path(settings.RAG_CHROMA_DIR), school_key, settings.RAG_EMBED_MODEL),
        collection=build_rag_vector_collection_name("fy_rag_chunks", settings.RAG_EMBED_MODEL),
        embed_model=settings.RAG_EMBED_MODEL,
    )


def _child_result_id(item: dict[str, Any]) -> str | None:
    metadata = _result_metadata(item)
    return item.get("id") or item.get("chunk_id") or metadata.get("id") or metadata.get("chunk_id")


def _parent_result_id(item: dict[str, Any], child_id: str) -> str:
    metadata = _result_metadata(item)
    return str(metadata.get("parent_id") or child_id)


def _aggregate_parent_results(items: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    parents: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for item in items:
        child_id = _child_result_id(item)
        if not child_id:
            continue

        metadata = _result_metadata(item)
        parent_id = _parent_result_id(item, str(child_id))
        parent_content = metadata.get("parent_content") or item.get("content", "")
        parent_doc_id = item.get("doc_id") or metadata.get("doc_id")
        parent_doc_name = item.get("doc_name") or metadata.get("doc_name")
        score = float(item.get("score", 0.0))

        if parent_id not in parents:
            parent_metadata = dict(metadata)
            parent_metadata.pop("parent_content", None)
            parent_metadata.pop("chunk_id", None)
            parents[parent_id] = {
                "id": parent_id,
                "doc_id": parent_doc_id,
                "doc_name": parent_doc_name,
                "content": parent_content,
                "metadata": parent_metadata,
                "score": 0.0,
                "matched_chunk_ids": [],
                "_best_child_score": score,
            }

        parent = parents[parent_id]
        parent["score"] += score
        parent["doc_id"] = parent.get("doc_id") or parent_doc_id
        parent["doc_name"] = parent.get("doc_name") or parent_doc_name
        if child_id not in parent["matched_chunk_ids"]:
            parent["matched_chunk_ids"].append(child_id)
        if score >= parent["_best_child_score"]:
            parent["_best_child_score"] = score
            parent["content"] = parent_content
            parent["metadata"].update({k: v for k, v in metadata.items() if k != "parent_content"})

    sorted_items = sorted(parents.values(), key=lambda x: x.get("score", 0.0), reverse=True)
    results: list[dict[str, Any]] = []
    for item in sorted_items[:top_k]:
        item.pop("_best_child_score", None)
        results.append(item)
    return results


def search(
    query: str,
    top_k: int = 5,
    vector_weight: float = 0.7,
    bm25_weight: float = 0.3,
    school_key: str | None = None,
    knowledge_base_id: str | None = None,
    *,
    aggregate_parents: bool = True,
) -> list[dict[str, Any]]:
    retriever = _get_retriever(school_key)
    child_top_k = max(top_k * 4, top_k)
    bm25_results = retriever.query(query, top_k=child_top_k, vector_weight=0.0, bm25_weight=1.0)

    vec_results: list[dict[str, Any]] = []
    try:
        vector_store = _get_vector_store(school_key)
        vec_results = vector_store.query(query, k=child_top_k)
    except Exception as exc:  # pragma: no cover
        logger.exception("RAG vector query failed for school %s: %s", school_key, exc)

    combined: dict[str, dict[str, Any]] = {}

    def _merge(items: list[dict], score_key: str, weight: float):
        for item in items:
            cid = _child_result_id(item)
            if cid is None:
                continue
            if cid not in combined:
                combined[cid] = {
                    "id": cid,
                    "doc_id": item.get("doc_id"),
                    "doc_name": item.get("doc_name"),
                    "content": item.get("content", ""),
                    "metadata": _result_metadata(item),
                    "score": 0.0,
                }
            combined[cid]["score"] += weight * float(item.get(score_key, 0.0))
            combined[cid]["doc_id"] = combined[cid].get("doc_id") or item.get("doc_id")
            combined[cid]["doc_name"] = combined[cid].get("doc_name") or item.get("doc_name")
            if not combined[cid]["content"]:
                combined[cid]["content"] = item.get("content", "")
            # merge metadata
            meta = _result_metadata(item)
            combined[cid]["metadata"].update(meta)

    _merge(vec_results, "score", vector_weight)
    _merge(bm25_results, "score", bm25_weight)

    strong_doc_ids: set[str] = set()
    for item in combined.values():
        boost = _query_match_boost(query, item)
        if boost <= 0:
            continue
        item["score"] += boost
        metadata = item.setdefault("metadata", {})
        metadata["_query_match_boost"] = boost
        doc_id = str(item.get("doc_id") or metadata.get("doc_id") or "").strip()
        if doc_id and boost >= 0.72:
            strong_doc_ids.add(doc_id)

    sorted_items = sorted(combined.values(), key=lambda x: x.get("score", 0), reverse=True)
    if knowledge_base_id:
        filtered_items: list[dict[str, Any]] = []
        for item in sorted_items:
            metadata = _result_metadata(item)
            item_knowledge_base_id = str(
                item.get("knowledge_base_id")
                or metadata.get("knowledge_base_id")
                or ""
            )
            if item_knowledge_base_id == knowledge_base_id:
                filtered_items.append(item)
        sorted_items = filtered_items
    if strong_doc_ids:
        focused_items = [
            item
            for item in sorted_items
            if str(item.get("doc_id") or (item.get("metadata") or {}).get("doc_id") or "").strip() in strong_doc_ids
        ]
        if focused_items:
            sorted_items = focused_items
    if not aggregate_parents:
        return sorted_items[:top_k]
    return _aggregate_parent_results(sorted_items, top_k)
