"""PostgreSQL-backed doc/chunk store for RAG uploads."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Optional
from bson import ObjectId
from app.db import PostgresCompatDatabase

from app.models.rag import DocRecord, ChunkRecord, KnowledgeBaseRecord

logger = logging.getLogger(__name__)

DOC_COLLECTION = "rag_documents"
CHUNK_COLLECTION = "rag_chunks"


def _as_obj_id(value: str | ObjectId):
    return ObjectId(value) if ObjectId.is_valid(str(value)) else value


class RagStore:
    def __init__(self, db: PostgresCompatDatabase):
        self.db = db

    @property
    def pool(self):
        return self.db.pool

    async def _ensure_collection(self, name: str) -> None:
        await self.db[name]._ensure_table()

    @staticmethod
    def _decode_json_field(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    @staticmethod
    def _normalize_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(value)

    def _normalize_metadata(self, value: Any) -> dict[str, Any]:
        decoded = self._decode_json_field(value)
        if isinstance(decoded, dict):
            return decoded
        if isinstance(decoded, str):
            decoded = decoded.strip()
            if not decoded:
                return {}
            reparsed = self._decode_json_field(decoded)
            if isinstance(reparsed, dict):
                return reparsed
            return {"raw": decoded}
        if decoded is None:
            return {}
        if isinstance(decoded, list):
            return {"items": decoded}
        return {"value": decoded}

    def _row_to_doc(self, row: Any) -> dict[str, Any]:
        doc = dict(row)
        metadata = doc.get("metadata")
        if metadata is not None:
            doc["metadata"] = self._decode_json_field(metadata)
        doc["id"] = str(doc.pop("_id"))
        return doc

    def _row_to_chunk(self, row: Any) -> dict[str, Any]:
        doc = dict(row)
        doc["id"] = str(doc.pop("_id"))
        doc["doc_id"] = self._normalize_text(doc.get("doc_id"))
        doc["knowledge_base_id"] = self._normalize_text(doc.get("knowledge_base_id"))
        doc["school_id"] = self._normalize_text(doc.get("school_id"))
        doc["admin_id"] = self._normalize_text(doc.get("admin_id"))
        doc["content"] = self._normalize_text(doc.get("content"))
        doc["metadata"] = self._normalize_metadata(doc.get("metadata"))
        return doc

    def _row_to_knowledge_base(self, row: Any) -> dict[str, Any]:
        doc = dict(row)
        doc["id"] = str(doc.pop("_id"))
        doc["name"] = self._normalize_text(doc.get("name"))
        doc["school_id"] = self._normalize_text(doc.get("school_id"))
        doc["admin_id"] = self._normalize_text(doc.get("admin_id"))
        doc["description"] = self._normalize_text(doc.get("description"))
        return doc

    async def save_doc(self, doc: DocRecord) -> None:
        payload = doc.model_dump(by_alias=True)
        payload["_id"] = doc.id
        await self.db[DOC_COLLECTION].insert_one(payload)

    async def create_knowledge_base(self, kb: KnowledgeBaseRecord) -> None:
        payload = kb.model_dump(by_alias=True)
        payload["_id"] = kb.id
        await self.db["rag_knowledge_bases"].insert_one(payload)

    async def update_doc(self, doc_id: str, **fields) -> None:
        await self._ensure_collection(DOC_COLLECTION)
        fields["updated_at"] = datetime.utcnow()
        if not fields:
            return
        assignments: list[str] = []
        values: list[Any] = []
        for index, (key, value) in enumerate(fields.items(), start=1):
            assignments.append(f"{key} = ${index}")
            if key == "metadata":
                values.append(json.dumps(value or {}, ensure_ascii=False))
            else:
                values.append(value)
        values.append(doc_id)
        sql = f"UPDATE rag_documents SET {', '.join(assignments)} WHERE _id = ${len(values)}"
        async with self.pool.acquire() as conn:
            await conn.execute(sql, *values)

    async def delete_doc(self, doc_id: str) -> dict[str, int]:
        await self._ensure_collection(DOC_COLLECTION)
        await self._ensure_collection(CHUNK_COLLECTION)
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                deleted_chunks = await conn.fetchval(
                    "SELECT COUNT(*) FROM rag_chunks WHERE doc_id = $1",
                    doc_id,
                )
                chunk_result = await conn.execute("DELETE FROM rag_chunks WHERE doc_id = $1", doc_id)
                doc_result = await conn.execute("DELETE FROM rag_documents WHERE _id = $1", doc_id)
        return {
            "deleted_chunks": int(deleted_chunks or 0),
            "deleted_chunk_rows": int(chunk_result.split()[-1]),
            "deleted_doc_rows": int(doc_result.split()[-1]),
        }

    async def list_docs(
        self,
        *,
        status: Optional[str] = None,
        search: Optional[str] = None,
        school_id: Optional[str] = None,
        knowledge_base_id: Optional[str] = None,
        limit: int = 200,
    ):
        conditions: list[str] = []
        values: list[Any] = []
        if school_id:
            values.append(school_id)
            conditions.append(f"school_id = ${len(values)}")
        if knowledge_base_id:
            values.append(knowledge_base_id)
            conditions.append(f"knowledge_base_id = ${len(values)}")
        if status:
            values.append(status)
            conditions.append(f"status = ${len(values)}")
        if search:
            values.append(f"%{search}%")
            conditions.append(f"name ILIKE ${len(values)}")
        where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        values.append(limit)
        await self._ensure_collection(DOC_COLLECTION)
        sql = f"""
            SELECT *
            FROM rag_documents
            {where_sql}
            ORDER BY created_at DESC NULLS LAST
            LIMIT ${len(values)}
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, *values)
        return [self._row_to_doc(row) for row in rows]

    async def get_doc(self, doc_id: str) -> Optional[dict]:
        await self._ensure_collection(DOC_COLLECTION)
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM rag_documents WHERE _id = $1", doc_id)
        if not row:
            return None
        return self._row_to_doc(row)

    async def get_knowledge_base(self, knowledge_base_id: str) -> Optional[dict]:
        await self._ensure_collection("rag_knowledge_bases")
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM rag_knowledge_bases WHERE _id = $1", knowledge_base_id)
        if not row:
            return None
        return self._row_to_knowledge_base(row)

    async def get_knowledge_base_by_name(self, *, school_id: str, name: str) -> Optional[dict]:
        await self._ensure_collection("rag_knowledge_bases")
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM rag_knowledge_bases
                WHERE school_id = $1 AND lower(name) = lower($2)
                LIMIT 1
                """,
                school_id,
                name,
            )
        if not row:
            return None
        return self._row_to_knowledge_base(row)

    async def list_knowledge_bases(self, *, school_id: str, limit: int = 200) -> list[dict]:
        await self._ensure_collection("rag_knowledge_bases")
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM rag_knowledge_bases
                WHERE school_id = $1
                ORDER BY created_at ASC NULLS LAST, _id ASC
                LIMIT $2
                """,
                school_id,
                limit,
            )
        return [self._row_to_knowledge_base(row) for row in rows]

    async def count_docs_by_knowledge_base(self, *, school_id: str) -> dict[str, int]:
        await self._ensure_collection(DOC_COLLECTION)
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT knowledge_base_id, COUNT(*) AS doc_count
                FROM rag_documents
                WHERE school_id = $1 AND knowledge_base_id IS NOT NULL
                GROUP BY knowledge_base_id
                """,
                school_id,
            )
        return {
            self._normalize_text(row["knowledge_base_id"]): int(row["doc_count"] or 0)
            for row in rows
            if row["knowledge_base_id"] is not None
        }

    async def add_chunks(self, chunks: list[ChunkRecord]) -> None:
        if not chunks:
            return
        payloads = []
        for c in chunks:
            data = c.model_dump(by_alias=True)
            data["_id"] = c.id
            payloads.append(data)
        await self.db[CHUNK_COLLECTION].insert_many(payloads)

    async def list_chunks(self, doc_id: str) -> list[dict]:
        await self._ensure_collection(CHUNK_COLLECTION)
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM rag_chunks
                WHERE doc_id = $1
                ORDER BY created_at ASC NULLS LAST, _id ASC
                """,
                doc_id,
            )
        items: list[dict[str, Any]] = []
        for row in rows:
            try:
                items.append(self._row_to_chunk(row))
            except Exception as exc:
                row_id = None
                try:
                    row_id = row.get("_id")
                except Exception:
                    row_id = None
                logger.warning("Skip malformed rag chunk row %s for doc %s: %s", row_id, doc_id, exc)
        return items

    async def get_chunk(self, chunk_id: str) -> Optional[dict]:
        await self._ensure_collection(CHUNK_COLLECTION)
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM rag_chunks WHERE _id = $1", chunk_id)
        if not row:
            return None
        return self._row_to_chunk(row)

    async def count_chunks(self, doc_id: str) -> int:
        await self._ensure_collection(CHUNK_COLLECTION)
        async with self.pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM rag_chunks WHERE doc_id = $1", doc_id)
        return int(count or 0)

    async def update_chunk(self, chunk_id: str, *, content: Optional[str] = None, metadata: Optional[dict] = None) -> bool:
        await self._ensure_collection(CHUNK_COLLECTION)
        updates: dict[str, Any] = {"updated_at": datetime.utcnow()}
        if content is not None:
            updates["content"] = content
        if metadata is not None:
            updates["metadata"] = metadata
        assignments: list[str] = []
        values: list[Any] = []
        for index, (key, value) in enumerate(updates.items(), start=1):
            assignments.append(f"{key} = ${index}")
            if key == "metadata":
                values.append(json.dumps(value or {}, ensure_ascii=False))
            else:
                values.append(value)
        values.append(chunk_id)
        sql = f"UPDATE rag_chunks SET {', '.join(assignments)} WHERE _id = ${len(values)}"
        async with self.pool.acquire() as conn:
            result = await conn.execute(sql, *values)
        return int(result.split()[-1]) > 0

    async def delete_chunk(self, chunk_id: str) -> bool:
        await self._ensure_collection(CHUNK_COLLECTION)
        async with self.pool.acquire() as conn:
            result = await conn.execute("DELETE FROM rag_chunks WHERE _id = $1", chunk_id)
        return int(result.split()[-1]) > 0
