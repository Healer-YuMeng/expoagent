"""Qwen 向量嵌入封装，走 OpenAI 兼容 Embeddings 接口。"""

from __future__ import annotations

from typing import Iterable, List

import httpx
from langchain_core.embeddings import Embeddings

from app.core.config import settings


class QwenEmbeddings(Embeddings):
    """符合 LangChain Embeddings 接口的 Qwen 实现。"""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        api_base: str | None = None,
        batch_size: int = 8,
        timeout: float = 30.0,
    ) -> None:
        if not api_key:
            raise ValueError("QwenEmbeddings 需要提供有效的 api_key")
        self._api_key = api_key
        self._model = model
        self._api_base = (api_base or settings.QWEN_API_BASE or "").rstrip("/")
        if not self._api_base:
            raise ValueError("QwenEmbeddings 需要配置 QWEN_API_BASE")
        self._batch_size = max(1, batch_size)
        self._timeout = timeout

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        return list(self._batch_generate(texts))

    def embed_query(self, text: str) -> List[float]:
        batches = self._batch_generate([text])
        return next(iter(batches))

    def _batch_generate(self, texts: Iterable[str]) -> Iterable[List[float]]:
        batch: list[str] = []
        for text in texts:
            batch.append("" if text is None else str(text))
            if len(batch) >= self._batch_size:
                yield from self._call_embedding(batch)
                batch = []
        if batch:
            yield from self._call_embedding(batch)

    def _call_embedding(self, batch: List[str]) -> Iterable[List[float]]:
        response = httpx.post(
            f"{self._api_base}/embeddings",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self._model,
                "input": batch,
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        embeddings = payload.get("data") or []
        if len(embeddings) != len(batch):
            raise RuntimeError("Qwen Embedding 返回的向量数量与输入不一致")
        for item in embeddings:
            embedding = item.get("embedding")
            if not isinstance(embedding, list):
                raise RuntimeError("Qwen Embedding 返回的向量格式不正确")
            yield embedding
