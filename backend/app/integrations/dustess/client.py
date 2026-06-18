"""尘锋 Dustess API 客户端、回调校验与调试能力。"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, Optional, Sequence

import httpx

from .config import get_settings
from .crypto import aes_decrypt, decode_aes_key, sha1_signature

logger = logging.getLogger(__name__)


class CFAgentConfigError(Exception):
    """尘锋 Agent 配置缺失或非法。"""


@dataclass
class AccessToken:
    token: str
    expires_at: float

    @property
    def is_valid(self) -> bool:
        return time.time() < self.expires_at - 300

    @property
    def expired(self) -> bool:
        return not self.is_valid


class CFAgentCrypto:
    """处理尘锋 Agent 回调签名与解密。"""

    def __init__(self, token: str, encoding_aes_key: str, receive_id: Optional[str] = None) -> None:
        if not token or not encoding_aes_key:
            raise CFAgentConfigError("缺少 token 或 encoding_aes_key")

        aes_key = decode_aes_key(encoding_aes_key)
        if len(aes_key) != 32:
            raise CFAgentConfigError("encoding_aes_key 长度非法，无法生成 256 bit 密钥")

        self._token = token
        self._aes_key = aes_key
        self._receive_id = receive_id

    def verify_url(self, msg_signature: str, timestamp: str, nonce: str, echo_str: str) -> str:
        return self.decrypt_message(msg_signature, timestamp, nonce, echo_str)

    def decrypt_message(self, msg_signature: str, timestamp: str, nonce: str, encrypted: str) -> str:
        signature = sha1_signature(self._token, timestamp, nonce, encrypted)
        if signature != msg_signature:
            raise ValueError("签名校验失败")

        decrypted = aes_decrypt(encrypted.replace(" ", "+"), self._aes_key)
        if len(decrypted) < 20:
            raise ValueError("解密结果长度异常")

        msg_len = int.from_bytes(decrypted[16:20], "big")
        msg = decrypted[20:20 + msg_len]
        receive_id = decrypted[20 + msg_len:].decode("utf-8")

        if self._receive_id and receive_id != self._receive_id:
            raise ValueError("receive_id 不匹配")

        return msg.decode("utf-8")


class DustessCallbackVerifier:
    """用于 GET 验证与 POST 回调的调试校验器。"""

    def __init__(self) -> None:
        settings = get_settings()
        token = settings.CF_AGENT_CALLBACK_TOKEN
        aes_key = settings.CF_AGENT_ENCODING_AES_KEY
        receive_id = settings.CF_AGENT_RECEIVE_ID
        if not token or not aes_key:
            raise RuntimeError("cf_agent_callback_token/cf_agent_encoding_aes_key 未配置")
        self._crypto = CFAgentCrypto(token=token, encoding_aes_key=aes_key, receive_id=receive_id)

    def verify_url(self, *, msg_signature: str, timestamp: str, nonce: str, echo_str: str) -> str:
        return self._crypto.verify_url(msg_signature, timestamp, nonce, echo_str)

    def decrypt_message(self, *, msg_signature: str, timestamp: str, nonce: str, encrypted: str) -> dict:
        text = self._crypto.decrypt_message(msg_signature, timestamp, nonce, encrypted)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"echostr": text}


class CFAgentClient:
    """尘锋 Agent API 客户端。"""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._lock = asyncio.Lock()
        self._access_token: Optional[AccessToken] = None

    @property
    def _base_url(self) -> str:
        return self.settings.CF_AGENT_BASE_URL.rstrip("/")

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def _client_id(self) -> Optional[str]:
        return self.settings.CF_AGENT_CLIENT_ID

    @property
    def _client_secret(self) -> Optional[str]:
        return self.settings.CF_AGENT_CLIENT_SECRET

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_data: dict | None = None,
    ) -> dict:
        url = f"{self._base_url}{path}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.request(method, url, params=params, json=json_data)
        resp.raise_for_status()
        data = resp.json()
        logger.debug("Dustess %s response: %s", path, data)
        return data

    async def get_access_token(self, force_refresh: bool = False) -> Optional[str]:
        """获取有效 access_token，内部自动缓存。"""
        if not self._client_id or not self._client_secret:
            logger.warning("尘锋 Agent clientId/clientSecret 未配置，跳过获取 access_token")
            return None

        async with self._lock:
            if not force_refresh and self._access_token and self._access_token.is_valid:
                return self._access_token.token

            payload = {
                "clientid": self._client_id,
                "clientsecret": self._client_secret,
            }
            try:
                data = await self._request("POST", "/auth/v1/access_token/token", json_data=payload)
            except Exception as exc:
                logger.error("获取尘锋 accessToken 失败: %s", exc)
                return None

            if data.get("code") != 0:
                logger.error("获取尘锋 accessToken 返回错误: %s", data)
                return None

            token = data.get("data", {}).get("accessToken")
            expires_in = data.get("data", {}).get("expiresIn")
            if not token:
                logger.error("尘锋 accessToken 响应缺少 token 字段: %s", data)
                return None

            expires_at = time.time() + 7200
            if expires_in:
                try:
                    expires_at = datetime.strptime(expires_in, "%Y-%m-%d %H:%M:%S").timestamp()
                except ValueError:
                    logger.debug("expiresIn 字段无法解析，使用默认过期时间")

            self._access_token = AccessToken(token=token, expires_at=expires_at)
            logger.info("成功刷新尘锋 accessToken，有效期至 %s", datetime.fromtimestamp(expires_at))
            return token

    async def _require_access_token(self, force_refresh: bool = False) -> str:
        access_token = await self.get_access_token(force_refresh=force_refresh)
        if not access_token:
            raise RuntimeError("无法获取 accessToken，请检查尘锋配置")
        return access_token

    @staticmethod
    def _normalize_maybe_int(value: Any) -> Any:
        try:
            return int(value)
        except (TypeError, ValueError):
            return value

    async def send_message(
        self,
        chat_id: Any,
        messages: list[dict],
        *,
        user_id: Any | None = None,
    ) -> bool:
        """通过 sendMsg 接口发送消息列表。"""
        if not messages:
            logger.warning("sendMsg 收到空消息列表，跳过发送")
            return False

        user_id = user_id or self.settings.CF_AGENT_USER_ID
        if not user_id:
            logger.warning("CF_AGENT_USER_ID 未配置，无法调用 sendMsg 接口")
            return False

        access_token = await self.get_access_token()
        if not access_token:
            return False

        formatted_msgs: list[dict] = []
        for item in messages:
            msg_type = item.get("msgType")
            if msg_type is None:
                raise ValueError("sendMsg 消息缺少 msgType 字段")
            contents = item.get("contents") or []
            if not isinstance(contents, list):
                raise ValueError("sendMsg 消息的 contents 必须为列表")

            formatted_msgs.append(
                {
                    "msgType": msg_type,
                    "contents": contents,
                    "fileURL": item.get("fileURL") or "",
                    "replyMsgID": item.get("replyMsgID") or [],
                }
            )

        payload = {
            "chatID": self._normalize_maybe_int(chat_id),
            "userID": self._normalize_maybe_int(user_id),
            "msgs": formatted_msgs,
        }
        params = {"accessToken": access_token}

        try:
            data = await self._request("POST", "/ai/v1/agent/msg/sendMsg", params=params, json_data=payload)
        except Exception as exc:
            logger.error("调用尘锋 sendMsg 接口失败: %s", exc)
            return False

        if data.get("code") != 0:
            logger.error("尘锋 sendMsg 返回错误: %s", data)
            return False

        logger.info("尘锋 sendMsg 成功，chat_id=%s，msgs=%s", chat_id, formatted_msgs)
        return True

    async def send_text_message(self, chat_id: Any, content: str) -> bool:
        if not content:
            logger.debug("尘锋 sendMsg 跳过发送空内容")
            return False
        return await self.send_message(chat_id, [{"msgType": 0, "contents": [content]}])

    async def send_agent_message(
        self,
        chat_id: str,
        msg_type: int,
        contents: Sequence[str],
        file_url: str | None = None,
        reply_msg_ids: Sequence[int] | None = None,
    ) -> dict:
        access_token = await self._require_access_token()
        user_id = self.settings.CF_AGENT_USER_ID
        if not user_id:
            raise RuntimeError("cf_agent_user_id 未配置")

        payload = {
            "chatID": self._normalize_maybe_int(chat_id),
            "userID": self._normalize_maybe_int(user_id),
            "msgs": [
                {
                    "msgType": msg_type,
                    "contents": list(contents),
                    "fileURL": file_url or "",
                    "replyMsgID": list(reply_msg_ids or []),
                }
            ],
        }
        params = {"accessToken": access_token}
        return await self._request("POST", "/ai/v1/agent/msg/sendMsg", params=params, json_data=payload)

    async def direct_send(
        self,
        messages: Sequence[Dict[str, Any]],
        *,
        target_type: str,
        target_ids: Iterable[str],
        qw_user_id: str | None = None,
        scrm_account_id: str | None = None,
    ) -> dict:
        access_token = await self._require_access_token()
        qw_user_id = qw_user_id or self.settings.CF_AGENT_TEST_QW_USER_ID
        scrm_account_id = scrm_account_id or self.settings.CF_AGENT_SCRM_ACCOUNT_ID
        if not qw_user_id or not scrm_account_id:
            raise RuntimeError("缺少 CF_AGENT_TEST_QW_USER_ID 或 CF_AGENT_SCRM_ACCOUNT_ID")

        payload = {
            "scrmAccountID": scrm_account_id,
            "qwUserId": qw_user_id,
            "targetType": target_type,
            "targetIds": list(target_ids),
            "messages": list(messages),
        }
        params = {"accessToken": access_token}
        return await self._request("POST", "/ai/v1/agent/msg/directSendMsg", params=params, json_data=payload)

    async def forward_proxy(
        self,
        method: str,
        path: str,
        *,
        params: Dict[str, Any] | None = None,
        json_data: Dict[str, Any] | None = None,
    ) -> dict:
        access_token = await self._require_access_token()
        query = dict(params or {})
        query.setdefault("accessToken", access_token)
        return await self._request(method, path, params=query, json_data=json_data)

    def get_token_status(self) -> dict[str, Any]:
        if not self._access_token:
            return {"token": None, "expires_at": None, "valid": False}
        return {
            "token": self._access_token.token,
            "expires_at": datetime.fromtimestamp(self._access_token.expires_at).isoformat(),
            "valid": self._access_token.is_valid,
        }


DustessClient = CFAgentClient
