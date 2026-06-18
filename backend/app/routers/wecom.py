"""
企业微信对接路由
处理企业微信回调事件，维护线索与企微之间的映射关系
"""
from __future__ import annotations
import logging
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Literal, Tuple, Any

from bson import ObjectId
from fastapi import APIRouter, Depends, Query, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.db import PostgresCompatDatabase, get_database
from app.integrations.wecom import (
    WeComLangchainService,
    WeComService,
    get_wecom_langchain_service,
    get_wecom_service,
)
from app.models.user import UserSchema
from app.models.lead import LeadSchema
from app.core.config import settings
from app.integrations.dustess import CFAgentCrypto, CFAgentConfigError
from app.integrations.dustess.event_utils import extract_message_from_payload
from app.services.cf_agent_service import get_cf_agent_crypto

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/wecom", tags=["企业微信"])

PHONE_REGEX = re.compile(r"(1[3-9]\d{9})")
WECOM_HISTORY_LIMIT = 200
STARWAY_HISTORY_LIMIT = 20
MARKER_REGEX = re.compile(r"\[\[(?:WECHAT_QR|APPOINTMENT)\]\]\{[^}]*\}")
CALLBACK_LOG = Path(__file__).resolve().parents[2] / "dustess_callback.log"


def _normalize_phone_value(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if len(digits) == 11 and digits.startswith("1"):
        return digits
    stripped = value.strip()
    return stripped or None


def _get_wecom_crypto() -> Optional[CFAgentCrypto]:
    crypto = get_cf_agent_crypto()
    if crypto:
        return crypto
    token = settings.WECOM_TOKEN
    aes_key = settings.WECOM_ENCODING_AES_KEY
    receive_id = settings.WECOM_RECEIVE_ID
    if not token or not aes_key or not receive_id:
        logger.warning("WeCom 回调未配置 token/encodingAESKey/receive_id，无法完成验证")
        return None
    try:
        return CFAgentCrypto(token=token, encoding_aes_key=aes_key, receive_id=receive_id)
    except CFAgentConfigError as exc:
        logger.error("WeCom 回调加解密配置错误: %s", exc)
        return None


def _extract_wecom_payload(raw: dict, crypto: Optional[CFAgentCrypto]) -> dict:
    if not raw:
        return {}
    body = raw.get("body") if isinstance(raw.get("body"), dict) else raw
    encrypt = body.get("encrypt")
    if not encrypt:
        payload = dict(body)
        payload["_raw_payload"] = raw
        return payload
    if not crypto:
        raise ValueError("收到加密回调但未配置解密参数")
    msg_signature = body.get("msgSignature") or raw.get("msg_signature")
    timestamp = body.get("timeStamp") or body.get("timestamp") or raw.get("timestamp")
    nonce = body.get("nonce")
    if not all([msg_signature, timestamp, nonce]):
        raise ValueError("加密回调缺少签名字段")
    plaintext = crypto.decrypt_message(
        msg_signature,
        str(timestamp),
        str(nonce),
        encrypt.replace(" ", "+"),
    )
    payload = json.loads(plaintext)
    payload["_raw_payload"] = raw
    return payload


def _log_callback_payload(payload: dict) -> None:
    try:
        CALLBACK_LOG.parent.mkdir(parents=True, exist_ok=True)
        with CALLBACK_LOG.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception as exc:  # pragma: no cover
        logger.warning("写入 WeCom 回调日志失败: %s", exc)


def _extract_qv_chat_id(*payloads: dict) -> Optional[str]:
    for payload in payloads:
        if not payload:
            continue
        for key in ("qv_chat_id", "chat_id", "qvchatid", "session_id", "chatid"):
            value = payload.get(key)
            if value:
                return str(value)
    return None


def _to_wecom_event(payload: dict) -> WeComEvent:
    """
    兼容真实 Agent 回调结构，将其转换为内部统一的 WeComEvent.
    """
    if not payload:
        raise ValueError("Empty payload")

    message = extract_message_from_payload(payload)
    if message:
        sender_id = message.get("sender_id") or message.get("chat_id")
        if not sender_id:
            raise ValueError("Missing sender_id in payload")

        raw = message.get("_raw_payload") or {}
        body = raw.get("body") or raw
        msg_container = body.get("msg") or {}
        if isinstance(msg_container, dict) and "msg" in msg_container:
            inner_msg = msg_container.get("msg") or {}
        else:
            inner_msg = msg_container if isinstance(msg_container, dict) else {}

        content = message.get("content") or inner_msg.get("content")
        if isinstance(content, dict):
            content = content.get("content") or content.get("text") or json.dumps(content, ensure_ascii=False)

        direction = "parent"
        sender_type = message.get("sender_type")
        if sender_type in (2, "teacher") or inner_msg.get("is_ai_user"):
            direction = "bot"

        sent_ts = inner_msg.get("create_ts") or inner_msg.get("msg_ts")
        if isinstance(sent_ts, str):
            try:
                sent_ts = int(sent_ts)
            except ValueError:
                sent_ts = None
        sent_at = datetime.utcfromtimestamp(sent_ts / 1000) if sent_ts else None

        chat_id = message.get("chat_id") or body.get("chat_id")
        contact_name = message.get("sender_name") or (inner_msg.get("talker_name") if isinstance(inner_msg, dict) else None)

        return WeComEvent(
            event_type="message",
            external_userid=str(sender_id),
            contact_name=contact_name,
            advisor_wechat_id=None,
            content=content,
            direction=direction,
            sent_at=sent_at,
            qv_chat_id=str(chat_id) if chat_id else None,
        )

    # 如果包含 _raw_payload，优先解析 body
    if "_raw_payload" in payload:
        inner = payload.get("_raw_payload") or {}
        body = inner.get("body")
        if body:
            payload = body

    if "msg" in payload:
        msg = payload["msg"] or {}
        event_type = payload.get("event", "message")
        return WeComEvent(
            event_type="message" if event_type == "AI_CHAT_MSG" else event_type or "message",
            external_userid=str(msg.get("talker_id")),
            contact_name=msg.get("talker_name"),
            advisor_wechat_id=str(payload.get("user_id")) if payload.get("user_id") is not None else None,
            content=msg.get("content"),
            direction="parent" if not msg.get("is_ai_user") else "bot",
            sent_at=datetime.utcfromtimestamp(msg.get("create_ts", datetime.utcnow().timestamp()) / 1000)
            if msg.get("create_ts") else None,
            qv_chat_id=_extract_qv_chat_id(msg, payload),
        )

    # 兼容旧结构，直接用字段构建
    return WeComEvent(**payload)


def _build_follow_up_owner(advisor: dict) -> dict:
    qr_image = advisor.get("qr_image") or advisor.get("qr_code")
    qr_url = None
    if qr_image:
        base = (settings.WECHAT_QR_BASE_URL or "").rstrip("/")
        qr_url = f"{base}/{qr_image.lstrip('/')}" if base else qr_image
    return {
        "name": advisor.get("teacher_name"),
        "campus": advisor.get("campus"),
        "wechat_id": advisor.get("wechat_id"),
        "qr_code_url": qr_url,
        "contact_phone": advisor.get("contact_phone"),
    }


def _get_advisor_by_wechat_id(wechat_id: Optional[str]) -> Optional[dict]:
    if not wechat_id:
        return None
    for advisor in settings.WECHAT_ADVISORS or []:
        if advisor.get("wechat_id") == wechat_id:
            return advisor
    return None


def _resolve_wechat_advisor(campus: Optional[str]) -> Optional[dict]:
    if not campus:
        return None
    campus = campus.strip()
    if not campus:
        return None
    advisors = settings.WECHAT_ADVISORS or []
    base_url = (settings.WECHAT_QR_BASE_URL or "").rstrip("/")
    for advisor in advisors:
        if advisor.get("campus") != campus:
            continue
        qr_image = advisor.get("qr_image")
        qr_url = f"{base_url}/{qr_image}" if qr_image else None
        return {
            "name": advisor.get("teacher_name"),
            "campus": campus,
            "wechat_id": advisor.get("wechat_id"),
            "qr_code_url": qr_url,
            "contact_phone": advisor.get("contact_phone"),
        }
    return None


class WeComEvent(BaseModel):
    """企业微信事件回调"""
    event_type: Literal["friend_add", "message"] = Field(default="message", description="事件类型")
    external_userid: str = Field(..., description="企业微信外部联系人ID")
    contact_name: Optional[str] = Field(default=None, description="企业微信昵称")
    qv_chat_id: Optional[str] = Field(default=None, description="企业微信聊天唯一标识（qvChatId）")
    advisor_wechat_id: Optional[str] = Field(default=None, description="负责老师的企微ID")
    content: Optional[str] = Field(default=None, description="消息内容")
    direction: Literal["parent", "teacher", "bot"] = Field(
        default="parent",
        description="消息方向"
    )
    sent_at: Optional[datetime] = Field(default=None, description="发送时间")


def _extract_phone(payload: Optional[str]) -> Optional[str]:
    if not payload:
        return None
    match = PHONE_REGEX.search(payload)
    if not match:
        return None
    return _normalize_phone_value(match.group(1))


async def _find_lead_by_phone(db: PostgresCompatDatabase, phone: str) -> Optional[dict]:
    normalized = _normalize_phone_value(phone)
    if not normalized:
        return None
    query = {
        "$or": [
            {"parent_phone": normalized},
            {"extracted_info.phone": normalized},
        ]
    }
    lead = await db.leads.find_one(query)
    if lead:
        return lead
    regex = re.escape(normalized)
    return await db.leads.find_one({
        "$or": [
            {"parent_phone": {"$regex": regex}},
            {"extracted_info.phone": {"$regex": regex}},
        ]
    })


async def _find_or_create_parent_user(
    db: PostgresCompatDatabase,
    phone: str,
    contact_name: Optional[str]
) -> UserSchema:
    normalized_phone = _normalize_phone_value(phone) or phone
    existing = await db.users.find_one({"phone": normalized_phone})
    if existing:
        existing["_id"] = str(existing["_id"])
        return UserSchema(**existing)

    user = UserSchema(
        phone=normalized_phone,
        role="parent",
        parent_name=contact_name,
        name=contact_name,
        is_active=True,
        is_guest=True,
    )
    user_dict = user.model_dump(by_alias=True, exclude={"id"})
    result = await db.users.insert_one(user_dict)
    user.id = str(result.inserted_id)
    return user


async def _find_or_create_wecom_conversation(
    db: PostgresCompatDatabase,
    parent_user: UserSchema,
    external_userid: str
) -> str:
    existing = await db.conversations.find_one({"wecom_contact_id": external_userid})
    if existing:
        return str(existing["_id"])

    now = datetime.utcnow()
    conv_doc = {
        "parent_id": ObjectId(parent_user.id),
        "message_count": 0,
        "created_at": now,
        "updated_at": now,
        "last_message_at": None,
        "status": "active",
        "channel": "wecom",
        "wecom_contact_id": external_userid,
    }
    result = await db.conversations.insert_one(conv_doc)
    return str(result.inserted_id)


async def _ensure_lead_for_phone(
    db: PostgresCompatDatabase,
    phone: str,
    contact_name: Optional[str],
    external_userid: str,
    follow_up_owner: Optional[dict],
    qv_chat_id: Optional[str],
) -> Tuple[dict, bool]:
    normalized_phone = _normalize_phone_value(phone)
    lead = await _find_lead_by_phone(db, normalized_phone or phone)
    if lead:
        return lead, False

    parent_user = await _find_or_create_parent_user(db, normalized_phone or phone, contact_name)
    conversation_id = await _find_or_create_wecom_conversation(db, parent_user, external_userid)

    lead_schema = LeadSchema(
        parent_id=parent_user.id,
        conversation_id=conversation_id,
        parent_phone=normalized_phone or phone,
        parent_name=contact_name or parent_user.parent_name,
        parent_email=None,
        source="wechat",
    )
    lead_schema.wecom_status = "pending"
    lead_schema.wecom_contact_id = external_userid
    lead_schema.wecom_contact_name = contact_name
    lead_schema.qv_chat_id = qv_chat_id
    if follow_up_owner:
        lead_schema.follow_up_owner = follow_up_owner

    lead_doc = lead_schema.model_dump(by_alias=True, exclude_none=True)
    result = await db.leads.insert_one(lead_doc)
    lead_doc["_id"] = result.inserted_id
    return lead_doc, True


async def _append_wecom_message(
    db: PostgresCompatDatabase,
    lead: dict,
    message: dict,
    update_fields: Optional[dict] = None,
) -> None:
    update_doc = {
        "$set": {"updated_at": datetime.utcnow()},
        "$push": {
            "wecom_chat_history": {
                "$each": [message],
                "$slice": -WECOM_HISTORY_LIMIT,
            }
        },
    }
    if update_fields:
        update_doc["$set"].update(update_fields)
    await db.leads.update_one({"_id": lead["_id"]}, update_doc)


async def _load_starway_history(
    db: PostgresCompatDatabase,
    lead: dict,
) -> list[dict]:
    chat_id = lead.get("chat_id") or lead.get("conversation_id")
    if not chat_id:
        return []
    candidates = [chat_id]
    if ObjectId.is_valid(chat_id):
        oid = ObjectId(chat_id)
        candidates.extend([oid, str(oid)])
    cursor = (
        db.messages.find({"conversation_id": {"$in": candidates}})
        .sort("_id", 1)
        .limit(STARWAY_HISTORY_LIMIT)
    )
    history: list[dict] = []
    async for msg in cursor:
        sender_type = (msg.get("sender_type") or "").lower()
        direction = "parent"
        if sender_type == "bot":
            direction = "bot"
        elif sender_type == "teacher":
            direction = "teacher"
        history.append(
            {
                "direction": direction,
                "content": msg.get("content", ""),
                "sent_at": msg.get("created_at"),
            }
        )
    return history


@router.get("/events", summary="企业微信回调验证")
async def verify_wecom_callback(
    msg_signature: str = Query(..., description="企业微信签名", alias="msg_signature"),
    timestamp: str = Query(..., alias="timestamp"),
    nonce: str = Query(..., alias="nonce"),
    echostr: Optional[str] = Query(None, alias="echostr"),
    echo_str: Optional[str] = Query(None, alias="echo_str"),
    crypto: Optional[CFAgentCrypto] = Depends(_get_wecom_crypto),
):
    payload_echostr = echostr or echo_str
    if not payload_echostr:
        raise HTTPException(status_code=422, detail="missing echostr")
    if not crypto:
        raise HTTPException(status_code=500, detail="WeCom 回调加解密参数未配置")
    try:
        plain = crypto.verify_url(msg_signature, timestamp, nonce, payload_echostr)
        return PlainTextResponse(plain)
    except Exception as exc:  # pragma: no cover
        logger.error("WeCom URL 验证失败: %s", exc)
        raise HTTPException(status_code=400, detail="invalid signature") from exc


@router.post("/events", summary="接收企业微信事件")
async def receive_wecom_event(
    request: Request,
    db: PostgresCompatDatabase = Depends(get_database),
    wecom_service: WeComService = Depends(get_wecom_service),
    wecom_ai_service: WeComLangchainService = Depends(get_wecom_langchain_service),
    crypto: Optional[CFAgentCrypto] = Depends(_get_wecom_crypto),
):
    """
    接收企业微信事件：
    - friend_add：发送欢迎语并提示家长提供手机号
    - message：记录消息内容，自动匹配线索并更新企微状态
    """
    try:
        raw_payload = await request.json()
    except Exception:
        raw_payload = {}
    try:
        payload = _extract_wecom_payload(raw_payload, crypto)
    except Exception as exc:
        logger.error("解析企微回调失败: %s", exc)
        raise HTTPException(status_code=400, detail="invalid payload") from exc

    _log_callback_payload(payload)

    event = _to_wecom_event(payload)

    if event.event_type == "friend_add":
        await wecom_service.send_phone_request(event.external_userid, event.qv_chat_id)
        logger.info("收到企微好友添加事件，已发送手机号确认消息: %s", event.external_userid)
        return {"message": "welcome_sent"}

    message_doc = {
        "id": str(ObjectId()),
        "external_userid": event.external_userid,
        "qv_chat_id": event.qv_chat_id,
        "direction": event.direction,
        "content": event.content or "",
        "sent_at": event.sent_at or datetime.utcnow(),
    }

    # 先按企业微信ID/qvChatId匹配
    lead_filters = [{"wecom_contact_id": event.external_userid}]
    if event.qv_chat_id:
        lead_filters.append({"qv_chat_id": event.qv_chat_id})
    normalized_phone = _normalize_phone_value(_extract_phone(event.content or ""))
    if normalized_phone:
        lead_filters.append({"parent_phone": normalized_phone})
        lead_filters.append({"extracted_info.phone": normalized_phone})
    lead_query = {"$or": lead_filters} if len(lead_filters) > 1 else lead_filters[0]
    lead = await db.leads.find_one(lead_query)
    matched_by_phone = False
    if normalized_phone:
        phone_lead = await _find_lead_by_phone(db, normalized_phone)
        if phone_lead:
            lead = phone_lead
            matched_by_phone = True
        else:
            # 未找到同手机号的线索时，忽略 qv_chat_id/wecom_contact_id 的旧线索，允许创建新线索
            lead = None
    phone_value = _extract_phone(event.content or "")
    normalized_phone_value = _normalize_phone_value(phone_value) if phone_value else None
    new_lead_created = False

    advisor = _get_advisor_by_wechat_id(event.advisor_wechat_id)
    follow_up_owner_payload = _build_follow_up_owner(advisor) if advisor else None

    if lead is None and phone_value:
        lead, created = await _ensure_lead_for_phone(
            db,
            phone_value,
            event.contact_name,
            event.external_userid,
            follow_up_owner_payload,
            event.qv_chat_id,
        )
        matched_by_phone = True
        new_lead_created = created

    if lead is None and phone_value and not matched_by_phone:
        lead = await _find_lead_by_phone(db, phone_value)
        matched_by_phone = lead is not None

    if lead is None:
        logger.warning("未能匹配企微消息所属的线索: %s", event.external_userid)
        await wecom_service.send_unmatched_prompt(event.external_userid, event.qv_chat_id)
        return {"message": "pending_match"}

    if not follow_up_owner_payload:
        lead_campus = lead.get("campus") or (lead.get("extracted_info") or {}).get("campus")
        follow_up_owner_payload = _resolve_wechat_advisor(lead_campus)

    if not matched_by_phone and normalized_phone_value:
        lead_phone = _normalize_phone_value(lead.get("parent_phone"))
        extracted_phone = _normalize_phone_value((lead.get("extracted_info") or {}).get("phone"))
        if normalized_phone_value in {lead_phone, extracted_phone}:
            matched_by_phone = True

    update_fields = {}
    if event.qv_chat_id:
        update_fields["qv_chat_id"] = event.qv_chat_id
    existing_phone = {
        _normalize_phone_value(lead.get("parent_phone")),
        _normalize_phone_value((lead.get("extracted_info") or {}).get("phone")),
    }
    if matched_by_phone or (normalized_phone_value and normalized_phone_value in existing_phone):
        matched_by_phone = True
        update_fields["wecom_status"] = "added"
        update_fields["wecom_contact_id"] = event.external_userid
        if normalized_phone_value:
            update_fields["parent_phone"] = normalized_phone_value
        if event.contact_name:
            update_fields["wecom_contact_name"] = event.contact_name
        if follow_up_owner_payload:
            update_fields["follow_up_owner"] = follow_up_owner_payload
    elif lead.get("wecom_contact_id") == event.external_userid and lead.get("wecom_status") != "added":
        update_fields["wecom_status"] = "added"
        if event.contact_name:
            update_fields["wecom_contact_name"] = event.contact_name
        if follow_up_owner_payload:
            update_fields["follow_up_owner"] = follow_up_owner_payload
    elif event.contact_name:
        update_fields["wecom_contact_name"] = event.contact_name

    if follow_up_owner_payload and "follow_up_owner" not in update_fields:
        update_fields["follow_up_owner"] = follow_up_owner_payload

    updated_lead_doc = dict(lead)
    updated_history = list(lead.get("wecom_chat_history") or [])
    updated_history.append(message_doc)
    if len(updated_history) > WECOM_HISTORY_LIMIT:
        updated_history = updated_history[-WECOM_HISTORY_LIMIT:]
    updated_lead_doc["wecom_chat_history"] = updated_history
    if update_fields:
        updated_lead_doc.update(update_fields)
    await _append_wecom_message(db, lead, message_doc, update_fields or None)
    # 再次兜底设置企微关联字段，避免上面的 $set 未生效时状态缺失
    if matched_by_phone:
        fallback_updates = {
            "wecom_status": "added",
            "wecom_contact_id": event.external_userid,
        }
        if event.qv_chat_id:
            fallback_updates["qv_chat_id"] = event.qv_chat_id
        if normalized_phone_value:
            fallback_updates["parent_phone"] = normalized_phone_value
        if event.contact_name:
            fallback_updates["wecom_contact_name"] = event.contact_name
        if follow_up_owner_payload:
            fallback_updates["follow_up_owner"] = follow_up_owner_payload
        await db.leads.update_one({"_id": lead["_id"]}, {"$set": fallback_updates})
        # 额外同步所有同手机号/同企微ID的线索，确保列表显示一致
        sync_filters = []
        if normalized_phone_value:
            sync_filters.append({"parent_phone": normalized_phone_value})
            sync_filters.append({"extracted_info.phone": normalized_phone_value})
        sync_filters.append({"wecom_contact_id": event.external_userid})
        if sync_filters:
            await db.leads.update_many({"$or": sync_filters}, {"$set": fallback_updates})
        updated_lead_doc.update(fallback_updates)
    logger.info("已记录企微消息，线索: %s", lead.get("_id"))

    should_trigger_ai = event.direction == "parent"

    if matched_by_phone:
        if new_lead_created:
            await wecom_service.send_unmatched_prompt(event.external_userid, event.qv_chat_id)
        else:
            await wecom_service.send_known_parent_message(event.external_userid, event.qv_chat_id)
            should_trigger_ai = False

    starway_history: list[dict] = []
    if should_trigger_ai:
        try:
            starway_history = await _load_starway_history(db, updated_lead_doc)
        except Exception as exc:  # pragma: no cover
            logger.warning("加载星途历史对话失败: %s", exc)

        reply = await wecom_ai_service.generate_reply(
            lead=updated_lead_doc,
            chat_history=updated_history,
            starway_history=starway_history,
        )
        if reply:
            await wecom_service.send_text(event.external_userid, reply, event.qv_chat_id)

    return {
        "message": "message_recorded",
        "lead_id": str(lead.get("_id")),
        "phone_matched": matched_by_phone,
        "lead_created": new_lead_created,
    }
