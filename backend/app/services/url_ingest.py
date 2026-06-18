"""URL ingestion: fetch HTML, extract text, chunk, and return sections."""

from __future__ import annotations

import httpx
import logging
import uuid
from dataclasses import dataclass
from bs4 import BeautifulSoup

from app.services.rag_chunking import build_parent_child_chunks

logger = logging.getLogger(__name__)


@dataclass
class UrlMeta:
    doc_id: str
    name: str
    source_url: str
    status: str = "pending"
    chunk_count: int = 0


class UrlIngestor:
    async def ingest(self, url: str) -> tuple[UrlMeta, list[dict]]:
        doc_id = str(uuid.uuid4())
        content = await self._fetch(url)
        text, title = self._extract_text(content, url)

        meta = UrlMeta(
            doc_id=doc_id,
            name=title or url,
            source_url=url,
            status="pending",
        )

        chunks = self._chunk(text, meta)
        meta.status = "ready"
        meta.chunk_count = len(chunks)
        return meta, chunks

    async def _fetch(self, url: str) -> str:
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text

    def _extract_text(self, html: str, url: str) -> tuple[str, str]:
        soup = BeautifulSoup(html, "html.parser")
        # drop scripts/styles
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        title = (soup.title.string if soup.title else "") or url
        # take text from common tags
        texts = []
        for tag in soup.find_all(["h1", "h2", "h3", "p", "li"]):
            text = tag.get_text(strip=True)
            if text:
                texts.append(text)
        body = "\n".join(texts)
        if not body.strip():
            body = soup.get_text(" ", strip=True)
        return body, title

    def _chunk(self, text: str, meta: UrlMeta) -> list[dict]:
        if not text.strip():
            return []
        docs = build_parent_child_chunks(
            text,
            metadata={
                "doc_id": meta.doc_id,
                "doc_name": meta.name,
                "source_url": meta.source_url,
            },
            parent_seed=meta.doc_id,
        )
        chunks: list[dict] = []
        for idx, d in enumerate(docs):
            metadata = dict(d.get("metadata") or {})
            metadata["section_index"] = 0
            metadata["chunk_index"] = idx
            chunks.append(
                {
                    "doc_id": meta.doc_id,
                    "doc_name": meta.name,
                    "content": d.get("content", ""),
                    "metadata": metadata,
                }
            )
        return chunks
