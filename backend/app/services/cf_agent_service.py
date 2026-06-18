"""Dustess 客户端服务封装（兼容旧导入路径）。"""
from __future__ import annotations

import logging
from typing import Optional

from app.core.config import settings
from app.integrations.dustess import CFAgentClient, CFAgentConfigError, CFAgentCrypto

logger = logging.getLogger(__name__)


cf_agent_client = CFAgentClient()


def get_cf_agent_client() -> CFAgentClient:
    """FastAPI 依赖注入使用的单例客户端。"""
    return cf_agent_client


def get_cf_agent_crypto() -> Optional[CFAgentCrypto]:
    """用于回调验签/解密的单例实例。"""
    token = settings.CF_AGENT_CALLBACK_TOKEN
    aes_key = settings.CF_AGENT_ENCODING_AES_KEY
    if not token or not aes_key:
        return None
    receive_id = settings.CF_AGENT_RECEIVE_ID
    try:
        return CFAgentCrypto(token=token, encoding_aes_key=aes_key, receive_id=receive_id)
    except CFAgentConfigError as exc:
        logger.error("初始化尘锋 Agent Crypto 失败: %s", exc)
    except Exception as exc:  # pragma: no cover
        logger.exception("初始化尘锋 Agent Crypto 异常: %s", exc)
    return None


__all__ = [
    "cf_agent_client",
    "get_cf_agent_client",
    "get_cf_agent_crypto",
    "CFAgentClient",
    "CFAgentCrypto",
    "CFAgentConfigError",
]
