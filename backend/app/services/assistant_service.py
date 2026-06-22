from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from app.db import PostgresCompatDatabase
from app.models.assistant import AssistantSchema


ASSISTANT_COLLECTION = "assistants"


class AssistantService:
    def __init__(self, db: PostgresCompatDatabase):
        self.db = db

    async def _ensure_collection(self) -> None:
        await self.db[ASSISTANT_COLLECTION]._ensure_table()

    @staticmethod
    def _normalize_text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @classmethod
    def _normalize_knowledge_base_ids(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, (list, tuple, set)):
            raw_items = list(value)
        else:
            raw_items = [value]
        items: list[str] = []
        seen: set[str] = set()
        for raw in raw_items:
            text = cls._normalize_text(raw)
            if not text or text in seen:
                continue
            seen.add(text)
            items.append(text)
        return items

    def _row_to_assistant(self, row: dict[str, Any]) -> dict[str, Any]:
        knowledge_base_ids = self._normalize_knowledge_base_ids(row.get("knowledge_base_ids"))
        if not knowledge_base_ids:
            legacy_knowledge_base_id = self._normalize_text(row.get("knowledge_base_id"))
            if legacy_knowledge_base_id:
                knowledge_base_ids = [legacy_knowledge_base_id]
        return {
            "id": str(row.get("_id")),
            "name": self._normalize_text(row.get("name")) or "",
            "school_id": self._normalize_text(row.get("school_id")) or "",
            "admin_id": self._normalize_text(row.get("admin_id")),
            "knowledge_base_id": knowledge_base_ids[0] if knowledge_base_ids else None,
            "knowledge_base_ids": knowledge_base_ids,
            "is_active": bool(row.get("is_active", True)),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    async def list_assistants(self, *, school_id: str | None = None) -> list[dict[str, Any]]:
        await self._ensure_collection()
        items: list[dict[str, Any]] = []
        query: dict[str, Any] = {}
        if school_id:
            query["school_id"] = school_id
        cursor = self.db[ASSISTANT_COLLECTION].find(query).sort("created_at", 1)
        async for row in cursor:
            items.append(self._row_to_assistant(row))
        return items

    async def get_assistant(self, assistant_id: str) -> Optional[dict[str, Any]]:
        await self._ensure_collection()
        row = await self.db[ASSISTANT_COLLECTION].find_one({"_id": assistant_id})
        if not row:
            return None
        return self._row_to_assistant(row)

    async def get_assistant_by_name(self, *, school_id: str, name: str) -> Optional[dict[str, Any]]:
        await self._ensure_collection()
        cursor = self.db[ASSISTANT_COLLECTION].find({"school_id": school_id}).sort("created_at", 1)
        normalized_name = name.strip().lower()
        async for row in cursor:
            if str(row.get("name") or "").strip().lower() == normalized_name:
                return self._row_to_assistant(row)
        return None

    async def create_assistant(
        self,
        *,
        name: str,
        school_id: str,
        admin_id: Optional[str] = None,
        knowledge_base_id: Optional[str] = None,
        knowledge_base_ids: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        await self._ensure_collection()
        assistant_id = str(uuid.uuid4())
        normalized_knowledge_base_ids = self._normalize_knowledge_base_ids(knowledge_base_ids)
        if not normalized_knowledge_base_ids:
            normalized_knowledge_base_ids = self._normalize_knowledge_base_ids(knowledge_base_id)
        assistant = AssistantSchema(
            _id=assistant_id,
            name=name,
            school_id=school_id,
            admin_id=admin_id,
            knowledge_base_id=normalized_knowledge_base_ids[0] if normalized_knowledge_base_ids else None,
            knowledge_base_ids=normalized_knowledge_base_ids,
        )
        await self.db[ASSISTANT_COLLECTION].insert_one(assistant.model_dump(by_alias=True, exclude_none=True))
        created = await self.get_assistant(assistant_id)
        return created or assistant.model_dump(by_alias=False)

    async def update_assistant(self, assistant_id: str, **fields) -> Optional[dict[str, Any]]:
        await self._ensure_collection()
        if "knowledge_base_ids" in fields:
            normalized_knowledge_base_ids = self._normalize_knowledge_base_ids(fields.get("knowledge_base_ids"))
            fields["knowledge_base_ids"] = normalized_knowledge_base_ids
            fields["knowledge_base_id"] = normalized_knowledge_base_ids[0] if normalized_knowledge_base_ids else None
        elif "knowledge_base_id" in fields:
            normalized_knowledge_base_ids = self._normalize_knowledge_base_ids(fields.get("knowledge_base_id"))
            fields["knowledge_base_ids"] = normalized_knowledge_base_ids
            fields["knowledge_base_id"] = normalized_knowledge_base_ids[0] if normalized_knowledge_base_ids else None
        update_fields = {
            key: value
            for key, value in fields.items()
            if value is not None or key in {"knowledge_base_id", "knowledge_base_ids"}
        }
        update_fields["updated_at"] = datetime.utcnow()
        result = await self.db[ASSISTANT_COLLECTION].update_one(
            {"_id": assistant_id},
            {"$set": update_fields},
        )
        if not result.matched_count:
            return None
        return await self.get_assistant(assistant_id)
