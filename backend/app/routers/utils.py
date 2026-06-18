from __future__ import annotations

from typing import Any, Dict

from bson import ObjectId


def build_lead_chat_lookup(chat_id: str) -> Dict[str, Any]:
    """
    构造用于查询线索中 chat_id / conversation_id 的过滤条件，
    兼容历史数据仍然存储 conversation_id 的情况。
    """
    if not chat_id:
        raise ValueError("chat_id is required for lookup")

    fields = ("chat_id", "conversation_id")
    conditions: list[dict] = []
    for field in fields:
        conditions.append({field: chat_id})

    if ObjectId.is_valid(chat_id):
        oid = ObjectId(chat_id)
        for field in fields:
            conditions.append({field: oid})
            conditions.append({field: str(oid)})

    if len(conditions) == 1:
        return conditions[0]
    return {"$or": conditions}
