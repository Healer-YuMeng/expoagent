"""尘锋回调事件处理工具。"""
from __future__ import annotations

from typing import Any, Dict, Optional

import hashlib


def generate_guest_phone(sender_id: str) -> str:
    """根据 sender_id 生成 11 位手机号占位符。"""
    digest = hashlib.sha256(sender_id.encode("utf-8")).hexdigest()
    digits = "".join(str(int(ch, 16) % 10) for ch in digest)
    return "1" + digits[:10]


def normalize_event_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    将尘锋回调的多种结构归一化。
    可能出现以下情况：
      - 顶层直接包含 event/action/body
      - 顶层包含 data 再嵌套 event/action/body
    """
    if not payload:
        return {}

    raw_payload = payload.get("_raw_payload") or payload

    if "data" in raw_payload and isinstance(raw_payload["data"], dict):
        candidate = raw_payload["data"]
        if isinstance(candidate, dict):
            merged = dict(candidate)
            merged.setdefault("event", raw_payload.get("event"))
            merged.setdefault("action", raw_payload.get("action"))
            merged["_raw_payload"] = raw_payload
            return merged

    normalized = dict(payload)
    normalized.setdefault("_raw_payload", raw_payload)
    return normalized


def extract_message_from_payload(payload: Dict[str, Any]) -> Optional[dict]:
    """
    从回调数据中提取标准化的消息结构，供后续处理。
    返回 dict 包含：
        chat_id, sender_id, sender_name, sender_type, content, msg_type, file_url, event, action
    """
    normalized = normalize_event_payload(payload)

    if "sender_type" in normalized and "content" in normalized:
        return normalized

    event = normalized.get("event")
    body = normalized.get("body")
    if not body:
        # 兼容已被展开的结构（顶层直接包含 chat_id/msg）
        if "chat_id" in normalized and "msg" in normalized:
            body = normalized
        else:
            return None

    chat_id = body.get("chat_id") or body.get("chatID")
    if chat_id is None:
        return None

    msg_container = body.get("msg") or {}
    if isinstance(msg_container, dict) and "msg" in msg_container:
        msg = msg_container.get("msg") or {}
    else:
        msg = msg_container
    if not isinstance(msg, dict):
        return None

    sender_type = msg.get("sender_type")
    if sender_type is None and "is_ai_user" in msg:
        sender_type = 0 if msg.get("is_ai_user") else 1

    content = (msg.get("content") or "").strip()
    file_url = msg.get("file_url")
    msg_type = msg.get("msg_type", 0)

    return {
        "event": event,
        "action": normalized.get("action"),
        "chat_id": str(chat_id),
        "chat_name": body.get("chat_name"),
        "chat_type": body.get("chat_type"),
        "chat_status": body.get("chat_status"),
        "chat_tag_names": body.get("chat_tag_names") or [],
        "sender_id": str(msg.get("talker_id") or msg.get("sender_id") or ""),
        "sender_name": msg.get("talker_name") or msg.get("sender_name"),
        "sender_type": sender_type,
        "msg_id": str(msg.get("id")) if msg.get("id") is not None else None,
        "msg_type": msg_type,
        "content": content,
        "file_url": file_url,
        "_raw_payload": normalized.get("_raw_payload") or payload,
    }
