"""Tencent embedding client with hash fallback."""

from __future__ import annotations

import hashlib
import logging
from typing import List

import numpy as np
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.hunyuan.v20230901 import hunyuan_client, models

from app.core.config import settings

logger = logging.getLogger(__name__)


def _hash_vector(text: str, dim: int = 1024) -> list[float]:
    h = hashlib.sha256(text.encode("utf-8", errors="ignore")).digest()
    rng = np.random.default_rng(int.from_bytes(h[:8], "big", signed=False))
    return rng.standard_normal(dim).tolist()


class EmbeddingClient:
    def __init__(self, model: str) -> None:
        self.model = model
        self.secret_id = settings.TENCENT_SECRET_ID
        self.secret_key = settings.TENCENT_SECRET_KEY
        self.region = settings.TENCENT_REGION or "ap-shanghai"
        self._client = None
        if self.secret_id and self.secret_key:
            try:
                cred = credential.Credential(self.secret_id, self.secret_key)
                httpProfile = HttpProfile()
                httpProfile.reqTimeout = 15
                clientProfile = ClientProfile()
                clientProfile.httpProfile = httpProfile
                self._client = hunyuan_client.HunyuanClient(cred, self.region, clientProfile)
                logger.info("Tencent embedding client initialized for region %s", self.region)
            except Exception as exc:  # pragma: no cover
                logger.warning("Init Hunyuan client failed, fallback to hash vectors: %s", exc)
                self._client = None

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        if not self._client:
            logger.warning("Tencent embedding client not ready, fallback to hash vectors")
            return [_hash_vector(t, dim=1024) for t in texts]
        embeddings: List[List[float]] = []
        for text in texts:
            try:
                req = models.GetEmbeddingRequest()
                req.Model = self.model
                req.Input = str(text)
                resp = self._client.GetEmbedding(req)
                if resp.Data and resp.Data[0].Embedding:
                    embeddings.append(resp.Data[0].Embedding)
                else:
                    embeddings.append(_hash_vector(str(text), dim=1024))
            except Exception as exc:  # pragma: no cover
                logger.warning("Tencent embedding failed for one text, fallback hash: %s", exc)
                embeddings.append(_hash_vector(str(text), dim=1024))
        return embeddings

    def embed_query(self, text: str) -> List[float]:
        return self.embed_texts([text])[0]
