import logging
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

from app.services.cf_agent_service import get_cf_agent_client, CFAgentClient


class WeComService:
    """企业微信对接服务"""

    PHONE_REQUEST_TEMPLATE = (
        "您好，我是我校招生老师。为方便匹配您的咨询记录，"
        "请您直接回复孩子家长的手机号，我们将立即安排专属顾问跟进～"
    )

    def __init__(self) -> None:
        self._agent_client: Optional[CFAgentClient] = get_cf_agent_client()

    async def send_text(self, external_userid: str, content: str, chat_id: Optional[str] = None) -> None:
        """向企业微信外部联系人发送文本消息。"""
        if not content:
            return
        if self._agent_client and chat_id:
            try:
                success = await self._agent_client.send_text_message(chat_id, content)
                if success:
                    logger.info("[WeCom] 向 chat_id=%s 发送消息成功", chat_id)
                    return
                logger.warning("[WeCom] 向 chat_id=%s 发送消息失败（返回 false）", chat_id)
            except Exception as exc:  # pragma: no cover
                logger.error("[WeCom] 发送消息异常: %s", exc)
        logger.info("[WeCom][fallback] 向 %s 发送消息: %s", external_userid, content)

    async def send_phone_request(self, external_userid: str, chat_id: Optional[str] = None) -> None:
        """发送首条手机号确认消息。"""
        await self.send_text(external_userid, self.PHONE_REQUEST_TEMPLATE, chat_id)

    async def send_known_parent_message(self, external_userid: str, chat_id: Optional[str] = None) -> None:
        """当手机号匹配到线索时的提示语。"""
        content = "我记得你，我们会尽快为您安排专属老师联系。"
        await self.send_text(external_userid, content, chat_id)

    async def send_unmatched_prompt(self, external_userid: str, chat_id: Optional[str] = None) -> None:
        """当手机号暂未匹配线索时的 AI 入口提示。"""
        content = (
            "感谢添加星途招生助手！为了更好地服务您，请告知：孩子年龄/就读年级、意向校区，以及您最想了解的问题，我会即时为您解答。"
        )
        await self.send_text(external_userid, content, chat_id)


@lru_cache
def get_wecom_service() -> WeComService:
    return WeComService()
