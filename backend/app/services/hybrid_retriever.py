"""Hybrid retriever: vector (hash fallback) + BM25."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Iterable, List, Optional

import jieba
import numpy as np
from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)


def _hash_vector(text: str, dim: int = 768) -> list[float]:
    # deterministic pseudo-vector based on hash
    h = hashlib.sha256(text.encode("utf-8", errors="ignore")).digest()
    rng = np.random.default_rng(int.from_bytes(h[:8], "big", signed=False))
    return rng.standard_normal(dim).tolist()


class JiebaTokenizer:
    def __init__(self, dict_path: Optional[str] = None) -> None:
        if dict_path and Path(dict_path).exists():
            jieba.set_dictionary(dict_path)

    def cut(self, text: str) -> list[str]:
        return [tok.strip() for tok in jieba.cut(text) if tok.strip()]


class HybridRetriever:
    def __init__(self, cache_path: Path, tokenizer: Optional[JiebaTokenizer] = None) -> None:
        self.cache_path = cache_path
        self.tokenizer = tokenizer or JiebaTokenizer()
        self._bm25: Optional[BM25Okapi] = None
        self._bm25_docs: list[list[str]] = []
        self._bm25_meta: list[dict[str, Any]] = []
        self._load_cache()

    def _load_cache(self) -> None:
        if not self.cache_path.exists():
            return
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            tokens = data.get("tokens") or []
            metas = data.get("meta") or []
            self._bm25_docs = tokens
            self._bm25_meta = metas
            if tokens:
                self._bm25 = BM25Okapi(tokens)
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to load BM25 cache: %s", exc)

    def _save_cache(self) -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"tokens": self._bm25_docs, "meta": self._bm25_meta}
            self.cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to save BM25 cache: %s", exc)

    def add_chunks(self, chunks: Iterable[dict]) -> None:
        new_tokens: list[list[str]] = []
        new_meta: list[dict[str, Any]] = []
        for chunk in chunks:
            text = chunk.get("content") or ""
            tokens = self.tokenizer.cut(text)
            new_tokens.append(tokens)
            new_meta.append(chunk)
        if new_tokens:
            self._bm25_docs.extend(new_tokens)
            self._bm25_meta.extend(new_meta)
            self._bm25 = BM25Okapi(self._bm25_docs)
            self._save_cache()

    def remove_chunk(self, chunk_id: str) -> None:
        keep_tokens = []
        keep_meta = []
        for tokens, meta in zip(self._bm25_docs, self._bm25_meta):
            if meta.get("id") == chunk_id:
                continue
            keep_tokens.append(tokens)
            keep_meta.append(meta)
        self._bm25_docs = keep_tokens
        self._bm25_meta = keep_meta
        self._bm25 = BM25Okapi(self._bm25_docs) if self._bm25_docs else None
        self._save_cache()

    def update_chunk(self, chunk: dict) -> None:
        self.remove_chunk(chunk.get("id"))
        self.add_chunks([chunk])

    def replace_all(self, chunks: Iterable[dict]) -> None:
        self._bm25_docs = []
        self._bm25_meta = []
        self._bm25 = None
        self.add_chunks(chunks)

    def query(self, question: str, top_k: int = 5, vector_weight: float = 0.7, bm25_weight: float = 0.3) -> list[dict]:
        tokens = self.tokenizer.cut(question)
        bm25_scores: dict[str, float] = {}
        if self._bm25 and tokens:
            scores = self._bm25.get_scores(tokens)
            if scores.size > 0:
                min_s, max_s = scores.min(), scores.max()
                for score, meta in zip(scores, self._bm25_meta):
                    if max_s > min_s:
                        norm = (score - min_s) / (max_s - min_s)
                    else:
                        norm = 0.0
                    bm25_scores[meta.get("id")] = norm

        # vector scores via hash fallback
        vec_scores: dict[str, float] = {}
        q_vec = np.array(_hash_vector(question))
        for meta in self._bm25_meta:
            c_vec = np.array(_hash_vector(meta.get("content", "")))
            if q_vec.size != c_vec.size:
                continue
            sim = np.dot(q_vec, c_vec) / (np.linalg.norm(q_vec) * np.linalg.norm(c_vec) + 1e-8)
            vec_scores[meta.get("id")] = (sim + 1) / 2  # scale to 0-1

        combined: list[tuple[str, float, dict]] = []
        ids = set(bm25_scores.keys()) | set(vec_scores.keys())
        for cid in ids:
            score = vector_weight * vec_scores.get(cid, 0.0) + bm25_weight * bm25_scores.get(cid, 0.0)
            meta = next((m for m in self._bm25_meta if m.get("id") == cid), None)
            if meta:
                combined.append((cid, score, meta))
        combined.sort(key=lambda x: x[1], reverse=True)
        results: list[dict] = []
        for cid, score, meta in combined[:top_k]:
            payload = dict(meta)
            payload["id"] = cid
            payload["score"] = score
            results.append(payload)
        return results
