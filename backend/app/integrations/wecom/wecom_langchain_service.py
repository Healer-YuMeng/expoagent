import logging
import re
from datetime import datetime
from dataclasses import dataclass
from textwrap import dedent
from typing import Optional, Sequence, Tuple

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama

from app.core.config import settings

logger = logging.getLogger(__name__)


WECOM_QV_PROMPT = dedent(
    """你是“星途”招生助手在企业微信渠道的自动回复老师，任务是读取已有线索信息、星途历史对话以及最近的企微聊天，判断还缺少哪些关键信息，并在 60-80 字内用中文回复家长。

已知线索字段（为空表示缺失）：
{lead_snapshot}

尚未掌握的关键信息：
{missing_fields}

星途历史对话（按时间顺序，可为空）：
{starway_history}

企微聊天记录（时间顺序）：
{chat_history}

行为准则：
1. 始终以真人老师口吻回复，避免模板化或条列式描述，不使用 Markdown。
2. 每次对话只推动一个最重要的问题，优先补齐缺失字段（手机号、家长称呼、孩子姓名/年龄、申请年级、意向校区、外籍身份、邮箱）。
3. 如家长刚提供了信息，先自然确认，再引导下一个缺失点。
4. 若关键信息已齐全，则给出下一步行动（例如安排老师致电或引导预约）。
5. 避免重复询问家长已经回答过的信息。
6. 当前沟通已经是在企业微信内，禁止提及二维码、扫码、[[WECHAT_QR]] 等字样，也不要要求家长再添加微信或扫描图片。
7. 全程使用纯文本回复，不要生成任何结构化标记。
"""
)

REQUIRED_FIELDS = [
    ("parent_phone", "家长手机号"),
    ("parent_name", "家长称呼"),
    ("student_name", "孩子姓名"),
    ("student_age", "孩子年龄"),
    ("grade_applying", "申请年级"),
    ("campus", "意向校区"),
    ("has_foreign_passport", "家庭国籍情况"),
    ("parent_email", "邮箱"),
]


@dataclass
class WeComAssistantConfig:
    provider: str
    chat_model: str
    temperature: float
    ollama_base_url: str
    openai_api_key: Optional[str]
    qwen_api_key: Optional[str]
    qwen_api_base: Optional[str]
    anthropic_api_key: Optional[str]
    anthropic_api_base: Optional[str]
    anthropic_version: str


class WeComLangchainService:
    """面向企微渠道的轻量 LLM 服务"""

    def __init__(self) -> None:
        provider = (settings.LLM_PROVIDER or "qwen").lower()
        self.cfg = WeComAssistantConfig(
            provider=provider,
            chat_model=settings.LANGCHAIN_CHAT_MODEL,
            temperature=settings.LANGCHAIN_CHAT_TEMPERATURE,
            ollama_base_url=settings.OLLAMA_BASE_URL or "http://localhost:11434",
            openai_api_key=settings.OPENAI_API_KEY,
            qwen_api_key=settings.QWEN_API_KEY,
            qwen_api_base=settings.QWEN_API_BASE,
            anthropic_api_key=settings.ANTHROPIC_API_KEY,
            anthropic_api_base=settings.ANTHROPIC_API_BASE,
            anthropic_version=settings.ANTHROPIC_VERSION,
        )

    # ------------------------------------------------------------------
    # 构造底层模型
    # ------------------------------------------------------------------
    def _build_chat_model(self):
        if self.cfg.provider == "openai":
            kwargs = {
                "model": self.cfg.chat_model,
                "temperature": self.cfg.temperature,
                "streaming": False,
            }
            if self.cfg.openai_api_key:
                kwargs["openai_api_key"] = self.cfg.openai_api_key
            return ChatOpenAI(**kwargs)
        if self.cfg.provider == "ollama":
            return ChatOllama(
                model=self.cfg.chat_model,
                temperature=self.cfg.temperature,
                base_url=self.cfg.ollama_base_url,
                streaming=False,
            )
        if self.cfg.provider == "qwen":
            kwargs = {
                "model": self.cfg.chat_model,
                "temperature": self.cfg.temperature,
                "streaming": False,
                "openai_api_base": self.cfg.qwen_api_base,
            }
            if self.cfg.qwen_api_key:
                kwargs["openai_api_key"] = self.cfg.qwen_api_key
                kwargs["api_key"] = self.cfg.qwen_api_key
            return ChatOpenAI(**kwargs)
        raise ValueError(f"Unsupported LLM provider: {self.cfg.provider}")

    def _build_anthropic_headers(self) -> dict[str, str]:
        if not self.cfg.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY 未配置")
        return {
            "x-api-key": self.cfg.anthropic_api_key,
            "anthropic-version": self.cfg.anthropic_version,
            "content-type": "application/json",
        }

    async def _anthropic_complete(self, messages: Sequence, *, max_tokens: int = 256) -> str:
        system_parts: list[str] = []
        payload_messages: list[dict[str, str]] = []
        for message in messages:
            role = getattr(message, "type", "") or ""
            content = self._normalize_text(getattr(message, "content", "")) or ""
            if not content:
                continue
            if role == "system":
                system_parts.append(content)
                continue
            payload_messages.append(
                {
                    "role": "assistant" if role in {"assistant", "ai"} else "user",
                    "content": content,
                }
            )
        payload = {
            "model": self.cfg.chat_model,
            "messages": payload_messages or [{"role": "user", "content": ""}],
            "max_tokens": max_tokens,
            "temperature": self.cfg.temperature,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                self.cfg.anthropic_api_base.rstrip("/") + "/v1/messages",
                headers=self._build_anthropic_headers(),
                json=payload,
            )
            response.raise_for_status()
        data = response.json()
        texts = [
            item.get("text", "")
            for item in (data.get("content") or [])
            if item.get("type") == "text"
        ]
        return "".join(texts).strip()

    # ------------------------------------------------------------------
    # 对话内容整理
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_text(content) -> Optional[str]:
        if content is None:
            return None
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(str(part) for part in content if part)
        return str(content)

    @staticmethod
    def _strip_markers(text: Optional[str]) -> str:
        if not text:
            return ""
        return re.sub(r"\[\[(?:WECHAT_QR|APPOINTMENT)\]\]\{[^}]*\}", "", text).strip()

    @staticmethod
    def _clean_reply(text: str) -> str:
        if not text:
            return ""
        sanitized = WeComLangchainService._strip_markers(text)
        for term in ("扫码", "扫描", "二维码", "QR", "加微", "加我微信"):
            sanitized = re.sub(rf"[^。！？]*{term}[^。！？]*[。！？]?", "", sanitized, flags=re.IGNORECASE)
        sanitized = sanitized.replace("[[", "").replace("]]", "")
        return sanitized.strip()

    @staticmethod
    def _format_lead_snapshot(lead: dict) -> str:
        lines: list[str] = []
        for key, label in REQUIRED_FIELDS:
            value = lead.get(key)
            if value is None or value == "":
                lines.append(f"{label}: —")
            else:
                lines.append(f"{label}: {value}")
        follow_up_owner = lead.get("follow_up_owner") or {}
        advisor_name = follow_up_owner.get("name")
        if advisor_name:
            lines.append(f"跟进老师: {advisor_name}")
        return "\n".join(lines) if lines else "暂无线索字段"

    @staticmethod
    def _format_missing_fields(lead: dict) -> str:
        missing: list[str] = []
        for key, label in REQUIRED_FIELDS:
            value = lead.get(key)
            if value is None or value == "":
                missing.append(label)
        return "、".join(missing) if missing else "（已收集完整信息）"

    @staticmethod
    @staticmethod
    def _coerce_datetime(value) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value)
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return datetime.utcnow()
        return datetime.utcnow()

    def _format_history(self, history: Sequence[dict]) -> Tuple[str, list[dict]]:
        if not history:
            return "暂无聊天记录", []
        # 仅保留最近 12 条，按时间排序
        sorted_history = sorted(history, key=lambda item: self._coerce_datetime(item.get("sent_at") or item.get("created_at")))
        recent = sorted_history[-12:]
        lines: list[str] = []
        for item in recent:
            role = item.get("direction") or "parent"
            speaker = "家长" if role == "parent" else "招生助手"
            content = self._strip_markers(item.get("content") or "")
            lines.append(f"{speaker}: {content.strip()}")
        return "\n".join(lines), recent

    def _format_starway_history(self, messages: Sequence[dict]) -> str:
        if not messages:
            return "暂无"
        ordered = sorted(messages, key=lambda item: self._coerce_datetime(item.get("sent_at")))
        recent = ordered[-12:]
        lines: list[str] = []
        for item in recent:
            role = item.get("direction") or "parent"
            speaker = "家长" if role == "parent" else "招生助手"
            content = self._strip_markers(item.get("content") or "")
            if not content:
                continue
            lines.append(f"{speaker}: {content}")
        return "\n".join(lines) if lines else "暂无"

    # ------------------------------------------------------------------
    # 对外能力
    # ------------------------------------------------------------------
    async def generate_reply(
        self,
        *,
        lead: dict,
        chat_history: Sequence[dict],
        starway_history: Optional[Sequence[dict]] = None,
    ) -> Optional[str]:
        """根据现有线索信息与企微&星途历史生成下一句回复"""
        if not chat_history:
            logger.debug("企微助手: 聊天记录为空，跳过自动回复")
            return None

        lead_snapshot = self._format_lead_snapshot(lead or {})
        missing_fields = self._format_missing_fields(lead or {})
        history_text, ordered_history = self._format_history(chat_history)
        starway_history_text = self._format_starway_history(starway_history or [])

        system_prompt = WECOM_QV_PROMPT.format(
            lead_snapshot=lead_snapshot,
            missing_fields=missing_fields,
            chat_history=history_text,
            starway_history=starway_history_text,
        )
        user_message = ""
        for item in reversed(ordered_history):
            if (item.get("direction") or "parent") == "parent":
                user_message = item.get("content") or ""
                break
        if not user_message and ordered_history:
            user_message = ordered_history[-1].get("content") or ""

        messages = [
            SystemMessage(content=system_prompt),
        ]
        if user_message:
            messages.append(HumanMessage(content=user_message.strip()))

        try:
            if self.cfg.provider == "anthropic":
                text = await self._anthropic_complete(messages)
            else:
                model = self._build_chat_model()
                response = await model.ainvoke(messages)
                text = getattr(response, "content", None)
                text = self._normalize_text(text)
            if not text:
                return None
            reply = self._clean_reply(text)
            if not reply:
                return None
            logger.info("企微助手自动回复生成成功: %s", reply)
            return reply
        except Exception as exc:  # pragma: no cover
            logger.error("企微助手生成回复失败: %s", exc)
            return None


_wecom_langchain_service = WeComLangchainService()


def get_wecom_langchain_service() -> WeComLangchainService:
    return _wecom_langchain_service
