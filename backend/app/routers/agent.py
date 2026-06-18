"""
尘锋 Agent 回调路由
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse

from app.db import PostgresCompatDatabase, get_database
from app.integrations.dustess import (
    CFAgentClient,
    CFAgentCrypto,
    extract_message_from_payload,
    generate_guest_phone,
)
from app.models.user import UserSchema
from app.routers.parent import (
    CreateConversationRequest,
    SendMessageRequest,
    create_conversation,
    send_message,
)
from app.services.cf_agent_service import get_cf_agent_client, get_cf_agent_crypto
from app.services.langchain_service import LangchainService, get_langchain_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agent", tags=["第三方Agent"])

SESSION_COLLECTION = "cf_agent_sessions"
CALLBACK_LOG = Path(__file__).resolve().parents[2] / "dustess_callback.log"


async def _ensure_guest_user(
    db: PostgresCompatDatabase,
    sender_id: str,
    nickname: Optional[str] = None,
) -> UserSchema:
    existing = await db.users.find_one({"anonymous_id": sender_id})
    if existing:
        existing["_id"] = str(existing["_id"])
        return UserSchema(**existing)

    now = datetime.utcnow()
    phone = generate_guest_phone(sender_id)
    user_doc = {
        "phone": phone,
        "password_hash": "",
        "role": "parent",
        "is_active": True,
        "created_at": now,
        "updated_at": now,
        "name": nickname or "访客家长",
        "anonymous_id": sender_id,
        "is_guest": True,
    }
    result = await db.users.insert_one(user_doc)
    user_doc["_id"] = str(result.inserted_id)
    return UserSchema(**user_doc)


async def _ensure_agent_conversation(
    db: PostgresCompatDatabase,
    user: UserSchema,
    chat_id: str,
) -> str:
    session = await db[SESSION_COLLECTION].find_one({"_id": chat_id})
    if session:
        return session["conversation_id"]

    return await _create_agent_conversation(db, user, chat_id)


async def _create_agent_conversation(
    db: PostgresCompatDatabase,
    user: UserSchema,
    chat_id: str,
) -> str:
    """强制创建新的会话，并更新映射。"""
    await db[SESSION_COLLECTION].delete_one({"_id": chat_id})

    created = await create_conversation(
        CreateConversationRequest(),
        current_user=user,
        db=db,
    )
    conversation_id = created.id
    now = datetime.utcnow()
    session_doc = {
        "_id": chat_id,
        "chat_id": chat_id,
        "conversation_id": conversation_id,
        "parent_id": user.id,
        "sender_id": user.anonymous_id,
        "created_at": now,
        "updated_at": now,
    }
    await db[SESSION_COLLECTION].insert_one(session_doc)
    return conversation_id


async def _consume_streaming_response(streaming_response) -> Dict[str, Any]:
    """消费父端 send_message 返回的 StreamingResponse，提取最终回复。"""
    result: Dict[str, Any] = {"answer": "", "chat_actions": []}
    body_iter = streaming_response.body_iterator
    try:
        async for chunk in body_iter:
            if isinstance(chunk, bytes):
                chunk_text = chunk.decode("utf-8")
            else:
                chunk_text = str(chunk)
            for line in chunk_text.strip().splitlines():
                line = line.strip()
                if not line.startswith("data: "):
                    continue
                try:
                    payload = json.loads(line[6:])
                except json.JSONDecodeError:
                    logger.debug("解析 SSE 行失败: %s", line)
                    continue
                if "answer" in payload:
                    result["answer"] += payload["answer"]
                elif payload.get("event") == "chat_action":
                    result["chat_actions"].append(payload.get("payload"))
                elif payload.get("event") == "done":
                    bot_message = payload.get("bot_message") or {}
                    result["bot_message"] = bot_message
    finally:
        aclose = getattr(body_iter, "aclose", None)
        if callable(aclose):
            await aclose()
    return result


def _extract_post_payload(raw: Dict[str, Any], crypto: Optional[CFAgentCrypto]) -> Dict[str, Any]:
    """从原始 POST 请求中提取业务负载，必要时执行解密。"""
    if not raw:
        return {}

    if "body" in raw and isinstance(raw["body"], dict):
        body = raw["body"]
    else:
        body = raw

    encrypt = body.get("encrypt")
    if not encrypt:
        payload = dict(body)
        if "event" not in payload and "event" in raw:
            payload["event"] = raw["event"]
        if "action" not in payload and "action" in raw:
            payload["action"] = raw["action"]
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
        msg_signature, str(timestamp), str(nonce), encrypt.replace(" ", "+")
    )
    payload = json.loads(plaintext)
    if "event" not in payload and "event" in raw:
        payload["event"] = raw["event"]
    if "action" not in payload and "action" in raw:
        payload["action"] = raw["action"]
    payload["_raw_payload"] = raw
    return payload


async def _process_agent_event(
    payload: Dict[str, Any],
    db: PostgresCompatDatabase,
    ai_service: LangchainService,
    agent_client: CFAgentClient,
) -> dict[str, Any]:
    try:
        CALLBACK_LOG.parent.mkdir(parents=True, exist_ok=True)
        with CALLBACK_LOG.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception as exc:  # pragma: no cover
        logger.warning("写入 Dustess 回调日志失败: %s", exc)

    message = extract_message_from_payload(payload)
    if not message:
        logger.warning("未能从回调中提取消息: %s", payload)
        return {"status": "ignored", "reason": "parse_failed"}

    sender_type = message.get("sender_type")
    if sender_type != 1:  # 只处理访客消息
        logger.info("忽略非访客消息: sender_type=%s", sender_type)
        return {"status": "ignored", "reason": "non_customer"}

    chat_id = message.get("chat_id") or ""
    sender_id = message.get("sender_id") or ""
    if not chat_id or not sender_id:
        logger.warning("回调缺少 chat_id 或 sender_id: %s", message)
        return {"status": "ignored", "reason": "missing_ids"}

    # 去重：同一个消息 ID 只处理一次
    msg_id = message.get("msg_id")
    session = await db[SESSION_COLLECTION].find_one({"_id": chat_id})
    if session and msg_id and session.get("last_msg_id") == msg_id:
        logger.info("检测到重复消息，忽略: chat_id=%s msg_id=%s", chat_id, msg_id)
        return {"status": "ignored", "reason": "duplicate", "chat_id": chat_id}

    msg_type = message.get("msg_type")
    content = message.get("content") or ""

    if msg_type != 0 and not content:
        logger.info("当前仅处理文本消息，msg_type=%s 跳过", msg_type)
        return {"status": "ignored", "reason": f"unsupported_msg_type:{msg_type}"}

    if not content:
        logger.info("收到空内容消息，chat_id=%s，跳过", chat_id)
        return {"status": "ignored", "reason": "empty_content"}

    nickname = message.get("sender_name")
    user = await _ensure_guest_user(db, sender_id=sender_id, nickname=nickname)
    if session:
        conversation_id = session["conversation_id"]
    else:
        conversation_id = await _create_agent_conversation(db, user, chat_id)

    # 持久化原始 payload 便于排查
    session_update = {
        "chat_name": message.get("chat_name"),
        "chat_type": message.get("chat_type"),
        "chat_status": message.get("chat_status"),
        "chat_tag_names": message.get("chat_tag_names"),
        "last_payload": message.get("_raw_payload"),
        "updated_at": datetime.utcnow(),
    }
    if msg_id:
        session_update["last_msg_id"] = msg_id
    await db[SESSION_COLLECTION].update_one(
        {"_id": chat_id},
        {"$set": session_update},
        upsert=True,
    )

    try:
        streaming_response = await send_message(
            conversation_id,
            SendMessageRequest(content=content),
            current_user=user,
            db=db,
            ai_service=ai_service,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            logger.warning("会话不存在，尝试重新创建: chat_id=%s", chat_id)
            conversation_id = await _create_agent_conversation(db, user, chat_id)
            streaming_response = await send_message(
                conversation_id,
                SendMessageRequest(content=content),
                current_user=user,
                db=db,
                ai_service=ai_service,
            )
        else:
            logger.warning("发送消息失败: %s", exc.detail)
            return {"status": "error", "reason": exc.detail, "code": exc.status_code}
    except Exception as exc:
        logger.exception("内部处理来访消息失败: %s", exc)
        return {"status": "error", "reason": str(exc)}

    result = await _consume_streaming_response(streaming_response)
    bot_message = result.get("bot_message") or {}
    reply_content = bot_message.get("content") or result.get("answer")
    if not reply_content:
        logger.warning("无法获取机器人最终回复，chat_id=%s", chat_id)
        return {"status": "error", "reason": "empty_reply"}

    await agent_client.send_text_message(chat_id, reply_content)
    return {
        "status": "processed",
        "chat_id": chat_id,
        "conversation_id": conversation_id,
        "reply": reply_content,
    }


async def _handle_agent_message(
    payload: Dict[str, Any],
    db: PostgresCompatDatabase,
    ai_service: LangchainService,
    agent_client: CFAgentClient,
) -> None:
    await _process_agent_event(payload, db, ai_service, agent_client)


# ======================================================================
# 路由定义
# ======================================================================


@router.get("/callback")
async def verify_callback(
    request: Request,
    crypto: Optional[CFAgentCrypto] = Depends(get_cf_agent_crypto),
):
    """处理尘锋回调地址的验证请求。"""
    if crypto is None:
        raise HTTPException(status_code=503, detail="尘锋回调解密未配置")

    params = request.query_params
    timestamp = params.get("timestamp") or params.get("timeStamp")
    nonce = params.get("nonce")
    msg_signature = params.get("msg_signature") or params.get("msgSignature")
    echo_str = params.get("echo_str")

    if not all([timestamp, nonce, msg_signature, echo_str]):
        raise HTTPException(status_code=400, detail="参数不完整")

    try:
        plaintext = crypto.verify_url(
            msg_signature,
            str(timestamp),
            str(nonce),
            echo_str.replace(" ", "+"),
        )
    except Exception as exc:
        logger.warning("尘锋 URL 校验失败: %s", exc)
        raise HTTPException(status_code=400, detail="验证失败") from exc

    return PlainTextResponse(content=plaintext, media_type="text/plain")


@router.post("/callback")
async def agent_callback(
    request: Request,
    db: PostgresCompatDatabase = Depends(get_database),
    ai_service: LangchainService = Depends(get_langchain_service),
    agent_client: CFAgentClient = Depends(get_cf_agent_client),
    crypto: Optional[CFAgentCrypto] = Depends(get_cf_agent_crypto),
):
    """处理尘锋推送的业务事件。"""
    try:
        raw_body = await request.json()
    except Exception:
        raw_body = {}

    try:
        payload = _extract_post_payload(raw_body, crypto)
    except Exception as exc:
        logger.error("解析尘锋回调失败: %s", exc)
        return JSONResponse({"code": 0, "msg": "invalid payload"}, status_code=400)

    result = await _process_agent_event(payload, db, ai_service, agent_client)
    return JSONResponse({"code": 1, "msg": "ok", "data": result})


@router.post("/debug/mock", summary="手动触发尘锋事件（调试）")
async def debug_mock_event(
    payload: Dict[str, Any],
    db: PostgresCompatDatabase = Depends(get_database),
    ai_service: LangchainService = Depends(get_langchain_service),
    agent_client: CFAgentClient = Depends(get_cf_agent_client),
):
    """
    直接投递尘锋事件到处理链路，便于不用企业微信的情况下验证逻辑。
    """
    result = await _process_agent_event(payload, db, ai_service, agent_client)
    return result


@router.get("/token/status", summary="查看尘锋 accessToken 状态")
async def get_token_status(
    agent_client: CFAgentClient = Depends(get_cf_agent_client),
):
    """返回当前缓存的 accessToken 及过期时间（仅用于调试）。"""
    return agent_client.get_token_status()
