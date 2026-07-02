"""
家长端路由
处理家长用户相关的会话、消息等接口
"""
import asyncio
import json
import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Optional, List, AsyncGenerator, Sequence
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from bson import ObjectId

from app.db import PostgresCompatDatabase, get_database
from app.models.user import UserSchema
from app.models.conversation import ConversationSchema
from app.models.message import MessageSchema
from app.core.dependencies import get_current_parent
from app.services.langchain_service import get_langchain_service, LangchainService
from app.services import rag_search
from app.services.rag_result_filter import filter_live_rag_results
from app.routers.utils import build_lead_chat_lookup
from app.services.assistant_service import AssistantService
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/parent", tags=["家长端"])


# ========== 请求/响应模型 ==========

class ConversationListResponse(BaseModel):
    """会话列表响应"""
    total: int = Field(..., description="总数")
    items: List[dict] = Field(..., description="会话列表")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页数量")


class ConversationDetailResponse(BaseModel):
    """会话详情响应"""
    id: str
    message_count: int
    last_message_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    school_id: Optional[str] = None
    assistant_id: Optional[str] = None
    ai_reply_enabled: bool = True
    appointment: Optional[dict] = None


class SendMessageRequest(BaseModel):
    """发送消息请求"""
    content: str = Field(..., description="消息内容", min_length=1, max_length=5000)
    language: str = Field(default="zh-CN", description="当前系统语言代码")
    school_id: Optional[str] = Field(default=None, description="学校ID，用于旧会话兜底知识库作用域")
    assistant_id: Optional[str] = Field(default=None, description="助手ID，用于旧会话兜底作用域")


class SendMessageResponse(BaseModel):
    """发送消息响应"""
    user_message: dict = Field(..., description="用户消息")
    bot_message: dict = Field(..., description="AI 回复消息")
    conversation_id: str = Field(..., description="会话 ID")


class MessageListResponse(BaseModel):
    """消息列表响应"""
    total: int = Field(..., description="总数")
    items: List[dict] = Field(..., description="消息列表")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页数量")
    conversation: dict = Field(..., description="会话信息")


class WelcomeMessageTextResponse(BaseModel):
    """当前语言的欢迎语响应"""
    language: str = Field(..., description="语言代码")
    content: str = Field(..., description="欢迎语文本")


class ParentAssistantListResponse(BaseModel):
    items: List[dict] = Field(default_factory=list, description="可选助手列表")
    selected_assistant_id: Optional[str] = Field(default=None, description="当前会话已绑定助手")
    school_id: Optional[str] = Field(default=None, description="当前作用域学校")


class CreateConversationRequest(BaseModel):
    """创建新会话请求"""
    language: str = Field(default="zh-CN", description="用户选择的语言代码")
    source: Optional[str] = Field(default=None, description="渠道来源缩写（xhs/dy等）")
    school_id: Optional[str] = Field(default=None, description="学校ID，用于区分校区")
    assistant_id: Optional[str] = Field(default=None, description="助手ID")


class UpdateConversationAssistantRequest(BaseModel):
    assistant_id: str = Field(..., description="助手ID")


VALID_CAMPUSES = {"浦东", "浦西", "临港"}
VALID_CHANNEL_SOURCES = {"xhs", "dy", "blbl", "wb", "gzh", "wxsp"}
APPOINTMENT_PATTERN = re.compile(r"\[\[APPOINTMENT\]\](\{.*?\})", re.DOTALL)
APPOINTMENT_CONFIRMED_TAG = "预约已确认"
DEFAULT_WELCOME_MESSAGES = {
    "zh-CN": "你好",
    "en": "Hello",
    "zh-TW": "你好",
    "ja": "こんにちは",
    "ko": "안녕하세요",
    "fr": "Bonjour",
    "es": "Hola",
    "ru": "Здравствуйте",
}
DEFAULT_WELCOME_MESSAGE = DEFAULT_WELCOME_MESSAGES["zh-CN"]
PROFILE_COLLECTION = "conversation_profiles"
SYSTEM_SETTINGS_COLLECTION = "system_settings"


def normalize_channel_source(raw: str | None) -> str | None:
    if not raw:
        return None
    normalized = raw.strip().lower()
    return normalized if normalized in VALID_CHANNEL_SOURCES else None


async def _ensure_ai_reply_auto_resumed(
    db: PostgresCompatDatabase,
    conversation: dict[str, Any] | None,
) -> dict[str, Any] | None:
    return conversation
WELCOME_MESSAGE_KEY = "chat_welcome_message"
DEFAULT_WELCOME_SCOPE = "default_school"
INVALID_CONTACT_PROMPTS = {
    "zh-CN": {
        "phone": "您提供的手机号格式似乎不太正确，麻烦您重新发送 11 位手机号，我再继续帮您安排。",
    },
    "en": {
        "phone": "The phone number you provided does not look correct. Please resend a valid 11-digit mobile number so I can continue helping you.",
    },
    "zh-TW": {
        "phone": "您提供的手機號碼格式似乎不太正確，麻煩您重新發送 11 位手機號碼，我再繼續幫您安排。",
    },
    "ja": {
        "phone": "ご入力いただいた携帯番号の形式が正しくないようです。11桁の携帯番号をもう一度お送りください。確認でき次第、引き続きご案内いたします。",
    },
    "ko": {
        "phone": "입력하신 휴대폰 번호 형식이 올바르지 않은 것 같습니다. 11자리 휴대폰 번호를 다시 보내 주시면 계속 도와드리겠습니다.",
    },
    "fr": {
        "phone": "Le format du numéro de téléphone portable que vous avez indiqué ne semble pas correct. Merci de renvoyer un numéro portable valide à 11 chiffres, et je poursuivrai l'organisation pour vous.",
    },
    "es": {
        "phone": "El formato del número de móvil que proporcionó no parece correcto. Por favor, vuelva a enviar un número de móvil válido de 11 dígitos y seguiré ayudándole con la gestión.",
    },
    "ru": {
        "phone": "Похоже, формат указанного вами номера телефона неверен. Пожалуйста, отправьте корректный 11-значный номер мобильного телефона, и я продолжу помогать вам с оформлением.",
    },
}
MANUAL_CALLBACK_FLAG = "manual_callback_required"
MANUAL_PROMPT_SENT_FLAG = "manual_prompt_sent"
AUTO_LEAD_SCOPE = "global"
AUTO_LEAD_PREFIX = "auto_lead"
MANUAL_CALLBACK_TAG = "需人工回访"
MANUAL_CALLBACK_COLLECTION = "manual_callbacks"
NO_SUMMARY_TEXT_ZH = "暂无有效信息"
DEFAULT_PARENT_DISPLAY_NAME = "访客家长"
INVALID_PARENT_NAME_KEYWORDS = (
    "你好",
    "您好",
    "老师",
    "招生",
    "学校",
    "咨询",
    "预约",
    "开放日",
    "校园",
    "校区",
    "浦东",
    "浦西",
    "临港",
    "家长",
    "hello",
    "hi",
    "thanks",
    "thank",
)
MANUAL_TRIGGER_KEYWORDS = (
    # === 人工服务类 ===
    "人工",
    "转人工",
    "人工服务",
    "人工老师",
    "人工顾问",
    "人工客服",
    "真人客服",
    "真人",
    "客服",
    "咨询师",
    "顾问",
    "招生老师",
    "manual",
    "human",
    "agent",
    "representative",
    "customer service",
    
    # === 电话回访类 ===
    "电话",
    "打电话",
    "回电",
    "致电",
    "来电",
    "联系我",
    "打给我",
    "call",
    "phone",
    "call me",
    "contact me",
    "reach me",
    
    # === 预约/线下类 ===
    "预约顾问",
    "预约咨询",
    "线下咨询",
    "面谈",
    "当面",
    "arrange",
    "schedule",
    
    # === 校园访问类 ===
    "参观",
    "访问",
    "到校",
    "实地",
    "visit",
    "tour",
    "campus visit",
    "on-site",
)

APPOINTMENT_STATE_OPEN_DAY = "开放日"
APPOINTMENT_STATE_CAMPUS_VISIT = "校园参观"
APPOINTMENT_STATE_NONE = "无预约"
APPOINTMENT_STATES = {
    APPOINTMENT_STATE_OPEN_DAY,
    APPOINTMENT_STATE_CAMPUS_VISIT,
    APPOINTMENT_STATE_NONE,
}
REQUIRED_PROFILE_KEYS = (
    "parent_name",
    "phone",
)
WECHAT_QR_SENT_FLAG = "wecom_qr_sent"
RECENT_OPEN_DAY_OPTIONS = [
    {
        "id": "A1",
        "label": "A1：2025/11/02（周日）09:30-11:30，浦东校区",
        "timeslot": "2025/11/02 09:30-11:30",
        "campus": "浦东",
        "description": "适合小学或双语课程家庭，安排课堂体验与校长交流。",
    },
    {
        "id": "A2",
        "label": "A2：2025/11/09（周日）13:30-15:30，浦西校区",
        "timeslot": "2025/11/09 13:30-15:30",
        "campus": "浦西",
        "description": "面向初中家庭，提供课程规划咨询与校园参观。",
    },
    {
        "id": "A3",
        "label": "A3：2025/11/16（周日）09:30-11:30，临港校区",
        "timeslot": "2025/11/16 09:30-11:30",
        "campus": "临港",
        "description": "重点面向关注 STEM 与留学方向的家庭，包含实验室参访。",
    },
]
PHONE_CANDIDATE_PATTERN = re.compile(r"(?<![\d@])(?:\+?86[-\s]?)?(1(?:[-\s]?\d){10})(?![\d@])")
LONG_DIGIT_SEQUENCE_PATTERN = re.compile(r"(?<![\d@])\d{11,}(?![\d@])")
MASKED_PHONE_PATTERN = re.compile(r"(?<![\d@])1\d{2}(?:[\s-]?[xX\*＊•·_]{2,6}[\s-]?)+\d{4}(?![\d@])")


def _extract_appointment_payloads(text: str) -> list[dict]:
    payloads: list[dict] = []
    if not text:
        return payloads
    for raw in APPOINTMENT_PATTERN.findall(text):
        candidate = raw.strip()
        try:
            data = json.loads(candidate)
            if isinstance(data, dict) and data.get("timeslot"):
                payloads.append(data)
        except json.JSONDecodeError:
            continue
    return payloads


def _resolve_wechat_advisor(campus: Optional[str]) -> Optional[dict]:
    """根据校区匹配企微顾问配置。"""
    if not campus:
        return None
    campus = campus.strip()
    if not campus:
        return None
    advisors = settings.WECHAT_ADVISORS or []
    base_url = settings.WECHAT_QR_BASE_URL.rstrip("/")
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


def _build_wechat_qr_message(
    info: dict,
    flags: dict,
    *,
    has_appointment: bool,
    appointment_doc: Optional[dict] = None,
) -> Optional[str]:
    """
    生成企微二维码提示消息，确保家长在提供手机号并完成预约后才发送，且每个会话仅一次。
    """
    campus = info.get("campus")
    if not campus or flags.get(WECHAT_QR_SENT_FLAG):
        return None
    if not has_appointment and not appointment_doc:
        return None
    phone = (info.get("phone") or (appointment_doc or {}).get("phone") or "").strip()
    if not phone:
        return None
    advisor = _resolve_wechat_advisor(campus)
    if not advisor or not advisor.get("qr_code_url"):
        return None
    payload = {
        "campus": advisor["campus"],
        "teacher_name": advisor["name"],
        "qr_url": advisor["qr_code_url"],
        "wechat_id": advisor.get("wechat_id"),
    }
    flags[WECHAT_QR_SENT_FLAG] = True
    message = (
        f"{advisor['name']}老师负责{advisor['campus']}校区的后续跟进，"
        "扫码下方企微二维码即可直接联系老师。"
        f"[[WECHAT_QR]]{json.dumps(payload, ensure_ascii=False)}"
    )
    return message


def _normalize_campus(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    cleaned = value.replace("校区", "").strip()
    for campus in VALID_CAMPUSES:
        if campus in cleaned:
            return campus
    return None


def _ensure_tag(tags: list[str], tag: str) -> list[str]:
    if tag not in tags:
        return [*tags, tag]
    return tags


def _contains_manual_keyword(text: Optional[str]) -> bool:
    if not text:
        return False
    lowered = str(text).lower()
    return any(keyword.lower() in lowered for keyword in MANUAL_TRIGGER_KEYWORDS)


def _latest_parent_history_message(history: Sequence[dict[str, Any]] | None) -> Optional[str]:
    if not history:
        return None
    for item in reversed(history):
        if (item.get("role") or "").lower() != "user":
            continue
        content = str(item.get("content") or "").strip()
        if content:
            return content
    return None


def _find_manual_callback_reason(
    query: str,
    documents: Sequence,
    history: Sequence[dict[str, Any]] | None = None,
) -> tuple[Optional[str], Optional[str]]:
    if _contains_manual_keyword(query):
        previous_query = _latest_parent_history_message(history) or query.strip()
        return query.strip(), previous_query
    for doc in documents or []:
        metadata = getattr(doc, "metadata", {}) or {}
        question = metadata.get("question")
        content = getattr(doc, "page_content", "") or ""
        if _contains_manual_keyword(question):
            reason = str(question).strip()
            return reason, reason
        if _contains_manual_keyword(content):
            reason = str(question or content[:120]).strip()
            return reason, reason
    return None, None


async def _maybe_record_manual_callback(
    db: PostgresCompatDatabase,
    conversation_id: str,
    parent: UserSchema,
    query: str,
    documents: Sequence,
    history: Sequence[dict[str, Any]] | None = None,
    profile_info: Optional[dict[str, Any]] = None,
) -> Optional[str]:
    reason, display_query = _find_manual_callback_reason(query, documents, history)
    if not reason:
        return None
    now = datetime.utcnow()
    parent_name = (
        _normalize_parent_name_candidate((profile_info or {}).get("parent_name"))
        or _normalize_parent_name_candidate(parent.parent_name)
        or _normalize_parent_name_candidate(parent.name)
        or DEFAULT_PARENT_DISPLAY_NAME
    )
    payload = {
        "conversation_id": conversation_id,
        "parent_id": parent.id,
        "parent_name": parent_name,
        "parent_phone": parent.phone,
        "reason": reason,
        "query": display_query or query,
        "updated_at": now,
    }
    await db[MANUAL_CALLBACK_COLLECTION].update_one(
        {"conversation_id": conversation_id},
        {
            "$set": payload,
            "$setOnInsert": {
                "created_at": now,
                "resolved": False,
            },
        },
        upsert=True,
    )
    logger.info("会话 %s 触发人工回访: %s", conversation_id, reason)
    return reason


def _welcome_key(school_id: str | None) -> str:
    return f"{WELCOME_MESSAGE_KEY}:{school_id or 'global'}"


async def _load_welcome_message_setting_doc(
    db: PostgresCompatDatabase,
    school_id: str | None = None,
) -> dict | None:
    candidate_keys: list[str] = []
    if school_id:
        candidate_keys.append(_welcome_key(school_id))
    candidate_keys.extend([
        _welcome_key(None),
        _welcome_key(DEFAULT_WELCOME_SCOPE),
    ])

    seen: set[str] = set()
    for key in candidate_keys:
        if key in seen:
            continue
        seen.add(key)
        doc = await db[SYSTEM_SETTINGS_COLLECTION].find_one({"_id": key})
        if doc:
            return doc

    return await db[SYSTEM_SETTINGS_COLLECTION].find_one(
        {"key": WELCOME_MESSAGE_KEY},
        sort=[("updated_at", -1)],
    )


def _default_welcome_message_for(language: str | None) -> str:
    if not language:
        return DEFAULT_WELCOME_MESSAGE
    if language in DEFAULT_WELCOME_MESSAGES:
        return DEFAULT_WELCOME_MESSAGES[language]
    if language.startswith("zh"):
        return DEFAULT_WELCOME_MESSAGES["zh-CN"]
    return DEFAULT_WELCOME_MESSAGES["en"]


def _invalid_contact_prompt_for(language: str | None, fields: set[str]) -> str:
    locale = language if language in INVALID_CONTACT_PROMPTS else None
    if not locale:
        locale = "zh-CN" if language and language.startswith("zh") else "en"
    return INVALID_CONTACT_PROMPTS[locale]["phone"]


def _invalid_contact_runtime_instruction_for(language: str | None, fields: set[str]) -> str:
    reply = _invalid_contact_prompt_for(language, fields)
    return (
        "系统校验结果：家长本轮提供的手机号格式不正确。"
        "不要把这次提供的联系方式当作已记录，不要继续索要其他新信息，也不要确认预约已完成。"
        f"请直接输出以下内容，不要添加任何其他文字：{reply}"
    )


def _resolve_welcome_message_from_value(value: Any, language: str | None) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None

    if not isinstance(value, dict):
        return None

    normalized: dict[str, str] = {}
    for lang, text in value.items():
        if not isinstance(lang, str):
            continue
        if not isinstance(text, str):
            continue
        stripped = text.strip()
        if stripped:
            normalized[lang] = stripped

    if not normalized:
        return None

    preferred_keys: list[str] = []
    if language:
        preferred_keys.append(language)
        if language.startswith("zh"):
            preferred_keys.extend(["zh-CN", "zh-TW"])
        else:
            base_lang = language.split("-")[0]
            preferred_keys.append(base_lang)

    preferred_keys.extend(["zh-CN", "en"])

    for key in preferred_keys:
        if key in normalized:
            return normalized[key]

    return next(iter(normalized.values()), None)


async def _load_welcome_message(db: PostgresCompatDatabase, language: str = "zh-CN", school_id: str | None = None) -> str:
    """从系统设置中加载欢迎语，根据语言返回对应版本。"""
    try:
        doc = await _load_welcome_message_setting_doc(db, school_id)
        if doc:
            resolved = _resolve_welcome_message_from_value(doc.get("value"), language)
            if resolved:
                return resolved
    except Exception as exc:  # pragma: no cover
        logger.warning("读取欢迎语失败，使用默认值: %s", exc)
    return _default_welcome_message_for(language)


def _normalize_has_appointment(value: Any) -> Optional[str]:
    """将预约字段归一化为固定枚举。"""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return APPOINTMENT_STATE_CAMPUS_VISIT if value else APPOINTMENT_STATE_NONE
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if "无" in text or text in {"不需要", "没预约", "未预约"}:
            return APPOINTMENT_STATE_NONE
        if "开放日" in text or text in {"open day", "open-day"}:
            return APPOINTMENT_STATE_OPEN_DAY
        if "参观" in text or "到校" in text or "visit" in text.lower():
            return APPOINTMENT_STATE_CAMPUS_VISIT
        if text in APPOINTMENT_STATES:
            return text
    return None


def _infer_appointment_type_from_doc(appointment_doc: Optional[dict[str, Any]], current_value: Optional[str]) -> Optional[str]:
    """根据预约文档推断预约类型，若已有有效值则优先保留。"""
    normalized_current = _normalize_has_appointment(current_value)
    if normalized_current in (APPOINTMENT_STATE_OPEN_DAY, APPOINTMENT_STATE_CAMPUS_VISIT):
        return normalized_current
    if not appointment_doc:
        return normalized_current
    timeslot = (appointment_doc.get("timeslot") or "").strip()
    for option in RECENT_OPEN_DAY_OPTIONS:
        if option["timeslot"] in timeslot or option["label"] in timeslot:
            return APPOINTMENT_STATE_OPEN_DAY
    return APPOINTMENT_STATE_CAMPUS_VISIT if timeslot else normalized_current


def _calculate_appointment_flag(extracted_info: Optional[dict], appointment_doc: Optional[dict[str, Any]]) -> bool:
    """计算 lead 顶层的 has_appointment 布尔值。"""
    if appointment_doc:
        return True
    state = _normalize_has_appointment((extracted_info or {}).get("has_appointment"))
    return state in (APPOINTMENT_STATE_OPEN_DAY, APPOINTMENT_STATE_CAMPUS_VISIT)


def _to_shanghai(dt: Optional[datetime]) -> Optional[datetime]:
    """将时间转换为上海时区，缺失则返回 None。"""
    if not dt:
        return None
    try:
        tz_utc = ZoneInfo("UTC")
        tz_sh = ZoneInfo("Asia/Shanghai")
    except Exception:
        return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz_utc)
    return dt.astimezone(tz_sh)


async def _get_first_parent_message_at(
    db: PostgresCompatDatabase,
    conversation_id: str,
    fallback: Optional[datetime] = None,
) -> Optional[datetime]:
    """获取家长在当前会话中的首条真实消息时间。"""
    candidates: list[Any] = [conversation_id]
    if ObjectId.is_valid(conversation_id):
        candidates.append(ObjectId(conversation_id))

    first_parent_message = await db.messages.find_one(
        {
            "conversation_id": {"$in": candidates},
            "sender_type": "parent",
        },
        sort=[("created_at", 1), ("_id", 1)],
    )
    if first_parent_message:
        first_created_at = first_parent_message.get("created_at")
        if isinstance(first_created_at, datetime):
            return _to_shanghai(first_created_at)

    return _to_shanghai(fallback) or _to_shanghai(datetime.utcnow())


def _build_auto_lead_id(parent_id: str, school_id: Optional[str]) -> str:
    scope = (school_id or AUTO_LEAD_SCOPE).strip() or AUTO_LEAD_SCOPE
    return f"{AUTO_LEAD_PREFIX}:{scope}:{parent_id}"


def _lead_identity_candidates(value: Optional[str]) -> list[Any]:
    if not value:
        return []
    candidates: list[Any] = [value]
    if ObjectId.is_valid(value):
        oid = ObjectId(value)
        candidates.extend([oid, str(oid)])
    unique_candidates: list[Any] = []
    seen: set[str] = set()
    for item in candidates:
        marker = repr(item)
        if marker in seen:
            continue
        seen.add(marker)
        unique_candidates.append(item)
    return unique_candidates


async def _find_existing_lead_for_parent(
    *,
    db: PostgresCompatDatabase,
    conversation_id: str,
    parent_id: str,
    school_id: Optional[str],
    parent_phone: Optional[str],
) -> Optional[dict]:
    lookups: list[dict[str, Any]] = [build_lead_chat_lookup(conversation_id)]
    parent_id_candidates = _lead_identity_candidates(parent_id)

    if school_id:
        if parent_id_candidates:
            lookups.append({"parent_id": {"$in": parent_id_candidates}, "school_id": school_id})
        if parent_phone:
            lookups.append({"parent_phone": parent_phone, "school_id": school_id})
        if parent_id_candidates:
            lookups.append({
                "parent_id": {"$in": parent_id_candidates},
                "$or": [{"school_id": None}, {"school_id": {"$exists": False}}],
            })
        if parent_phone:
            lookups.append({
                "parent_phone": parent_phone,
                "$or": [{"school_id": None}, {"school_id": {"$exists": False}}],
            })
    else:
        if parent_id_candidates:
            lookups.append({"parent_id": {"$in": parent_id_candidates}})
        if parent_phone:
            lookups.append({"parent_phone": parent_phone})

    for lookup in lookups:
        lead = await db.leads.find_one(lookup, sort=[("updated_at", -1), ("created_at", -1)])
        if lead:
            return lead
    return None


async def _find_lead_for_ai_reply_scope(
    *,
    db: PostgresCompatDatabase,
    conversation_id: str,
    parent_id: str,
    school_id: Optional[str],
) -> Optional[dict]:
    if conversation_id:
        lead = await db.leads.find_one(
            build_lead_chat_lookup(conversation_id),
            {"_id": 1, "ai_reply_enabled": 1, "school_id": 1, "parent_id": 1},
            sort=[("updated_at", -1), ("created_at", -1)],
        )
        if lead:
            return lead

    auto_lead_id = _build_auto_lead_id(parent_id, school_id)
    lead = await db.leads.find_one(
        {"_id": auto_lead_id},
        {"_id": 1, "ai_reply_enabled": 1, "school_id": 1, "parent_id": 1},
    )
    if lead:
        return lead

    parent_id_candidates = _lead_identity_candidates(parent_id)
    if not parent_id_candidates:
        return None

    lookup: dict[str, Any] = {"parent_id": {"$in": parent_id_candidates}}
    if school_id:
        lookup["school_id"] = school_id
    return await db.leads.find_one(
        lookup,
        {"_id": 1, "ai_reply_enabled": 1, "school_id": 1, "parent_id": 1},
        sort=[("updated_at", -1), ("created_at", -1)],
    )


def _has_complete_profile(info: Optional[dict]) -> bool:
    if not info:
        return False
    for key in REQUIRED_PROFILE_KEYS:
        if not info.get(key):
            return False
    return True


async def _load_assistant(db: PostgresCompatDatabase, assistant_id: Optional[str]) -> Optional[dict]:
    if not assistant_id:
        return None
    return await AssistantService(db).get_assistant(assistant_id)


def _normalize_message_assistant_id(message_doc: dict[str, Any]) -> str | None:
    metadata = message_doc.get("metadata") or {}
    if not isinstance(metadata, dict):
        return None
    assistant_id = str(metadata.get("assistant_id") or "").strip()
    return assistant_id or None


def _should_include_message_in_assistant_history(
    message_doc: dict[str, Any],
    assistant_id: str | None,
) -> bool:
    if not assistant_id:
        return True

    sender_type = str(message_doc.get("sender_type") or "")
    if sender_type == "parent":
        return True

    # 在助手严格隔离模式下，只保留当前助手自己生成的历史回复。
    # 这样即便同一会话曾切换过其他助手，也不会把旧助手的回答继续喂给当前助手。
    return _normalize_message_assistant_id(message_doc) == assistant_id


async def _resolve_conversation_school_scope(
    db: PostgresCompatDatabase,
    *,
    conversation: dict,
    fallback_school_id: Optional[str] = None,
) -> tuple[Optional[str], Optional[dict], bool]:
    school_id = (conversation.get("school_id") or "").strip() or None
    assistant_id = (conversation.get("assistant_id") or "").strip() or None
    assistant = None
    inferred_from_assistant = False

    if assistant_id:
        assistant = await _load_assistant(db, assistant_id)
        if assistant and not school_id:
            school_id = (assistant.get("school_id") or "").strip() or None
            inferred_from_assistant = bool(school_id)

    if not school_id:
        school_id = (fallback_school_id or "").strip() or None

    return school_id, assistant, inferred_from_assistant


async def _load_conversation_profile(db: PostgresCompatDatabase, conv_id: ObjectId) -> dict:
    """加载或初始化会话画像缓存，用于跨轮记忆家长信息。"""
    profile = await db[PROFILE_COLLECTION].find_one({"_id": conv_id})
    if profile is None:
        existing_conv = await db.conversations.find_one({"_id": conv_id})
        initial_info = {}
        if existing_conv:
            initial_info = dict(existing_conv.get("extracted_info") or {})
        profile = {
            "_id": conv_id,
            "info": initial_info,
            "flags": {},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        await db[PROFILE_COLLECTION].insert_one(profile)
    else:
        profile.setdefault("info", {})
        profile.setdefault("flags", {})
    return profile


async def _save_conversation_profile(
    db: PostgresCompatDatabase,
    conv_id: ObjectId,
    info: dict,
    flags: Optional[dict] = None,
) -> None:
    """写回会话画像缓存。"""
    now = datetime.utcnow()
    update_doc = {
        "$set": {
            "info": info,
            "updated_at": now,
        },
        "$setOnInsert": {
            "created_at": now,
        },
    }
    if flags is not None:
        update_doc["$set"]["flags"] = flags
    await db[PROFILE_COLLECTION].update_one({"_id": conv_id}, update_doc, upsert=True)


def _normalize_parent_name_candidate(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if candidate in {"招生助手", "助手"}:
        return None
    if len(candidate) > 20:
        return None
    lowered = candidate.lower()
    if any(keyword in lowered for keyword in INVALID_PARENT_NAME_KEYWORDS):
        return None
    if re.search(r"\d", candidate):
        return None
    if re.search(r"[，。！？、,:;@/\\]", candidate):
        return None
    if not re.fullmatch(r"[A-Za-z\u4e00-\u9fa5·\s]{2,20}", candidate):
        return None
    return candidate


def _extract_explicit_parent_name(text: str) -> Optional[str]:
    patterns = (
        r"(?:我叫|我是|叫我|姓名是|姓名|名字是|名字|称呼我|称呼)\s*[:：]?\s*([A-Za-z\u4e00-\u9fa5·]{2,20})",
        r"(?:my name is|i am|i'm|this is)\s+([A-Za-z][A-Za-z\s]{1,19})",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        normalized = _normalize_parent_name_candidate(match.group(1))
        if normalized:
            return normalized
    return None


def _fallback_extract_info(merged: dict, transcript: str) -> dict:
    """在结构化提取失败时，用正则兜底提取关键字段。"""
    updated = {**(merged or {})}
    parent_only_lines = [
        line.split(":", 1)[1].strip()
        for line in (transcript or "").splitlines()
        if line.startswith("家长:")
    ]
    parent_only_text = "\n".join(parent_only_lines)

    if "phone" not in updated:
        normalized_phone = _normalize_phone_value(parent_only_text or transcript)
        if normalized_phone:
            updated["phone"] = normalized_phone

    if not updated.get("parent_name"):
        explicit_name = _extract_explicit_parent_name(parent_only_text or transcript)
        if explicit_name:
            updated["parent_name"] = explicit_name

    if "campus" not in updated:
        for campus in VALID_CAMPUSES:
            if campus in parent_only_text:
                updated["campus"] = campus
                break

    if not updated.get("student_age"):
        age_match = re.search(r"(?:年龄|Age|age)\D{0,3}(\d{1,2})", transcript)
        if age_match:
            try:
                age_val = int(age_match.group(1))
                if 0 < age_val <= 25:
                    updated["student_age"] = age_val
            except ValueError:
                pass

    if updated.get("has_foreign_passport") is None:
        inferred_foreign_passport = _infer_foreign_passport_status(parent_only_text or transcript)
        if inferred_foreign_passport is not None:
            updated["has_foreign_passport"] = inferred_foreign_passport

    if not updated.get("has_appointment"):
        lowered = transcript.lower()
        if "预约" in transcript:
            if "开放日" in transcript or "open day" in lowered:
                updated["has_appointment"] = APPOINTMENT_STATE_OPEN_DAY
            elif any(keyword in transcript for keyword in ("参观", "到校", "来校")) or "campus visit" in lowered:
                updated["has_appointment"] = APPOINTMENT_STATE_CAMPUS_VISIT
        elif "open day" in lowered:
            updated["has_appointment"] = APPOINTMENT_STATE_OPEN_DAY
        elif "campus visit" in lowered or "visit campus" in lowered:
            updated["has_appointment"] = APPOINTMENT_STATE_CAMPUS_VISIT

    return updated


def _extract_phone_candidate(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    for match in PHONE_CANDIDATE_PATTERN.finditer(value):
        compact = re.sub(r"\D", "", match.group(0))
        if compact.startswith("86") and len(compact) == 13:
            compact = compact[2:]
        if len(compact) == 11 and compact.startswith("1"):
            return compact
    return None


def _normalize_phone_value(value: Any) -> Optional[str]:
    return _extract_phone_candidate(value)


def _normalize_email_value(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    return candidate if re.fullmatch(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", candidate) else None


def _contains_masked_phone_candidate(text: str) -> bool:
    if not isinstance(text, str) or not text:
        return False
    return MASKED_PHONE_PATTERN.search(text) is not None


def _detect_invalid_contact_fields(text: str) -> set[str]:
    fields: set[str] = set()
    if not text:
        return fields
    lowered = text.lower()
    digit_count = len(re.findall(r"\d", text))
    mentions_phone = any(keyword in lowered for keyword in ("手机", "手机号", "电话", "phone", "mobile", "contact"))
    has_valid_phone = _normalize_phone_value(text) is not None
    has_long_digit_sequence = LONG_DIGIT_SEQUENCE_PATTERN.search(text) is not None
    has_masked_phone = _contains_masked_phone_candidate(text)
    if not has_valid_phone:
        if has_masked_phone:
            fields.add("phone")
        elif mentions_phone and digit_count > 0:
            fields.add("phone")
        elif has_long_digit_sequence:
            fields.add("phone")
    return fields


def _sanitize_contact_fields(info: dict) -> tuple[dict, set[str]]:
    sanitized = dict(info or {})
    invalid_fields: set[str] = set()

    if "phone" in sanitized:
        normalized_phone = _normalize_phone_value(sanitized.get("phone"))
        if normalized_phone:
            sanitized["phone"] = normalized_phone
        else:
            sanitized.pop("phone", None)
            invalid_fields.add("phone")

    return sanitized, invalid_fields

def _clean_extracted_info(info: dict) -> dict:
    """清洗从 LLM 提取的结构化信息，修复常见错误。"""
    cleaned_info = info.copy()

    # 清洗 phone 字段
    if phone_val := cleaned_info.get("phone"):
        cleaned_info["phone"] = _normalize_phone_value(phone_val)

    # 清洗 parent_name
    cleaned_info["parent_name"] = _normalize_parent_name_candidate(cleaned_info.get("parent_name"))
    
    if "student_age" in cleaned_info:
        age_val = cleaned_info.get("student_age")
        if isinstance(age_val, str):
            if age_val.isdigit():
                cleaned_info["student_age"] = int(age_val)
            else:
                cleaned_info["student_age"] = None
        elif isinstance(age_val, (int, float)):
            try:
                age_int = int(age_val)
                cleaned_info["student_age"] = age_int if 0 < age_int <= 25 else None
            except (TypeError, ValueError):
                cleaned_info["student_age"] = None

    if "has_appointment" in cleaned_info:
        cleaned_info["has_appointment"] = _normalize_has_appointment(cleaned_info.get("has_appointment"))

    if "campus" in cleaned_info:
        cleaned_info["campus"] = _normalize_campus(cleaned_info.get("campus"))

    return cleaned_info



def _needs_manual_callback(info: dict) -> bool:
    """根据提取的信息判断是否需要人工回访。"""
    has_foreign_passport = (info or {}).get("has_foreign_passport")
    # 如果外籍身份状态未知或明确为非外籍，则需要人工介入确认资格
    if has_foreign_passport is False:
        return True
    return False


def _infer_foreign_passport_status(text: str) -> Optional[bool]:
    if not text:
        return None
    lowered = text.lower()

    negative_patterns = (
        r"中国籍",
        r"中国国籍",
        r"中国护照",
        r"大陆籍",
        r"内地籍",
        r"本地籍",
        r"不是外籍",
        r"非外籍",
        r"没有外籍",
        r"无外籍",
        r"没有外国护照",
        r"无外国护照",
        r"chinese passport",
        r"not foreign",
        r"no foreign passport",
    )
    positive_patterns = (
        r"外籍",
        r"外國籍",
        r"外国护照",
        r"外籍护照",
        r"foreign passport",
        r"foreign national",
        r"港澳台",
        r"香港",
        r"澳门",
        r"macau",
        r"macao",
        r"taiwan",
        r"台湾",
        r"美国",
        r"英国",
        r"加拿大",
        r"澳大利亚",
        r"新加坡",
        r"日本",
        r"韩国",
        r"russian",
        r"american",
        r"british",
    )

    if any(re.search(pattern, text, re.IGNORECASE) for pattern in negative_patterns):
        return False
    if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in positive_patterns):
        return True
    return None


def _build_transcript_from_history(history: Sequence[dict], query: str, answer: str) -> str:
    lines: list[str] = []
    for item in history or []:
        role = (item.get("role") or "").lower()
        content = (item.get("content") or "").strip()
        if not content:
            continue
        speaker = "家长" if role == "user" else "助手"
        lines.append(f"{speaker}: {content}")
    if query.strip():
        lines.append(f"家长: {query.strip()}")
    if answer.strip():
        lines.append(f"助手: {answer.strip()}")
    return "\n".join(lines)


async def _postprocess_parent_reply(
    *,
    db: PostgresCompatDatabase,
    ai_service: LangchainService,
    conversation: ConversationSchema,
    conversation_id: str,
    conv_id: ObjectId,
    conv_snapshot: dict,
    current_user: UserSchema,
    locale: str,
    profile_info: dict,
    profile_flags: dict,
    prev_info_complete: bool,
    manual_callback_triggered: bool,
) -> None:
    try:
        transcript_lines: list[str] = []
        cursor = db.messages.find({"conversation_id": conversation.id}).sort("_id", 1)
        async for msg_doc in cursor:
            sender_type = msg_doc["sender_type"]
            speaker = "家长" if sender_type == "parent" else "助手"
            transcript_lines.append(f"{speaker}: {msg_doc['content']}")
        transcript = "\n".join(transcript_lines)

        structured_info = await ai_service.extract_structured_info(transcript=transcript) or {}
        structured_info = _clean_extracted_info(structured_info)

        merged_info = dict(profile_info)
        if structured_info:
            for key in ["parent_name", "phone"]:
                value = structured_info.get(key)
                if value is None or value == "":
                    continue
                merged_info[key] = value

        merged_info = _fallback_extract_info(merged_info, transcript)
        merged_info, invalid_contact_fields = _sanitize_contact_fields(merged_info)
        if "has_appointment" in merged_info:
            merged_info["has_appointment"] = _normalize_has_appointment(merged_info.get("has_appointment"))

        info_complete = _has_complete_profile(merged_info)
        flag_from_info = _needs_manual_callback(merged_info)
        needs_manual_callback_flag = flag_from_info or manual_callback_triggered
        if needs_manual_callback_flag:
            profile_flags[MANUAL_CALLBACK_FLAG] = True

        appointment_payloads = _extract_appointment_payloads(transcript)
        appointment_doc = None
        if appointment_payloads:
            appointment_doc = _build_appointment_doc(appointment_payloads[-1], merged_info, str(current_user.id))
            if appointment_doc:
                inferred_state = _infer_appointment_type_from_doc(
                    appointment_doc,
                    merged_info.get("has_appointment"),
                )
                if inferred_state:
                    merged_info["has_appointment"] = inferred_state
                if not merged_info.get("parent_name") and appointment_doc.get("guardian_name"):
                    merged_info["parent_name"] = appointment_doc["guardian_name"]
                if not merged_info.get("phone") and appointment_doc.get("phone"):
                    merged_info["phone"] = appointment_doc["phone"]
                if not merged_info.get("campus") and appointment_doc.get("campus"):
                    merged_info["campus"] = appointment_doc["campus"]
                info_complete = _has_complete_profile(merged_info)

        phone_value = merged_info.get("phone")

        current_time = datetime.utcnow()
        message_total = await db.messages.count_documents({"conversation_id": conversation.id})
        first_parent_message_at = await _get_first_parent_message_at(
            db,
            conversation.id,
            fallback=conversation.created_at,
        )
        update_data = {
            "message_count": message_total,
            "last_message_at": current_time,
            "updated_at": current_time,
        }
        if appointment_doc:
            update_data["appointment"] = appointment_doc

        previous_has_state = profile_info.get("has_appointment") if profile_info else None
        previous_info_complete = prev_info_complete
        await db.conversations.update_one({"_id": conv_id}, {"$set": update_data})
        await _save_conversation_profile(db, conv_id, merged_info, profile_flags)
        has_appointment_flag = _calculate_appointment_flag(merged_info, appointment_doc)

        summary = await ai_service.summarize_conversation(transcript)
        summary_text = summary.strip() if summary else NO_SUMMARY_TEXT_ZH

        from app.models.lead import LeadSchema, AppointmentInfo

        is_high_intent = bool(appointment_doc) or needs_manual_callback_flag
        lead_tags = []
        campus = merged_info.get("campus")
        if campus in VALID_CAMPUSES:
            lead_tags.append(campus)
        source_channel = conversation.source_channel

        if appointment_doc:
            lead_tags.append(APPOINTMENT_CONFIRMED_TAG)
        if needs_manual_callback_flag:
            lead_tags.append(MANUAL_CALLBACK_TAG)

        appointment_parent_name = (appointment_doc or {}).get("parent_name")
        appointment_phone = (appointment_doc or {}).get("phone")
        lead_parent_name = merged_info.get("parent_name") or appointment_parent_name or current_user.name
        lead_parent_phone = phone_value or appointment_phone
        advisor_payload = _resolve_wechat_advisor(merged_info.get("campus"))
        existing_lead = await _find_existing_lead_for_parent(
            db=db,
            conversation_id=conversation_id,
            parent_id=str(current_user.id),
            school_id=conversation.school_id if conversation else None,
            parent_phone=lead_parent_phone,
        )

        should_refresh_en_summary = (
            bool(summary_text)
            and (
                not existing_lead
                or existing_lead.get("summary") != summary_text
                or not (existing_lead.get("en_summary") or "").strip()
            )
        )
        if should_refresh_en_summary:
            en_summary_text = await ai_service.translate_summary_to_english(summary_text)
        else:
            en_summary_text = existing_lead.get("en_summary") if existing_lead else None

        if not existing_lead:
            source_value = source_channel or "chatbot"
            auto_lead_id = _build_auto_lead_id(str(current_user.id), conversation.school_id if conversation else None)
            lead = LeadSchema(
                _id=auto_lead_id,
                parent_id=str(current_user.id),
                parent_name=lead_parent_name,
                parent_phone=lead_parent_phone,
                school_id=conversation.school_id if conversation else None,
                campus=merged_info.get("campus"),
                conversation_id=conversation_id,
                source=source_value,
                is_high_intent=is_high_intent,
                needs_manual_callback=needs_manual_callback_flag,
                summary=summary_text,
                en_summary=en_summary_text,
                extracted_info=merged_info,
                tags=lead_tags,
                appointment=AppointmentInfo(**appointment_doc) if appointment_doc else None,
                has_foreign_passport=merged_info.get("has_foreign_passport", False),
                student_age=merged_info.get("student_age"),
                has_appointment=has_appointment_flag,
                follow_up_owner=advisor_payload,
                first_message_at=first_parent_message_at,
            )

            lead_dict = lead.model_dump(by_alias=True, exclude_none=True)
            created_at = lead_dict.pop("created_at", None)
            await db.leads.update_one(
                {"_id": auto_lead_id},
                {
                    "$set": lead_dict,
                    "$setOnInsert": {"created_at": created_at},
                },
                upsert=True,
            )
            logger.info("自动创建或收敛线索成功，家长: %s", lead_parent_name or "未提供姓名")
        else:
            updates = {"updated_at": datetime.utcnow()}
            if first_parent_message_at:
                updates["first_message_at"] = first_parent_message_at
            if not existing_lead.get("school_id") and conversation.school_id:
                updates["school_id"] = conversation.school_id
            if merged_info:
                updates["extracted_info"] = merged_info
                if lead_parent_name:
                    updates["parent_name"] = lead_parent_name
                if merged_info.get("has_foreign_passport") is not None:
                    updates["has_foreign_passport"] = merged_info["has_foreign_passport"]
                if merged_info.get("campus") in VALID_CAMPUSES:
                    updates["campus"] = merged_info["campus"]
                if merged_info.get("student_age") is not None:
                    updates["student_age"] = merged_info["student_age"]
                if lead_parent_phone:
                    updates["parent_phone"] = lead_parent_phone
            if (
                existing_lead.get("parent_id") != str(current_user.id)
                and (
                    not existing_lead.get("parent_id")
                    or (
                        lead_parent_phone
                        and existing_lead.get("parent_phone") == lead_parent_phone
                    )
                )
            ):
                updates["parent_id"] = str(current_user.id)
            if advisor_payload:
                updates["follow_up_owner"] = advisor_payload
            updates["has_appointment"] = has_appointment_flag

            if appointment_doc:
                updates["appointment"] = appointment_doc
                existing_tags = existing_lead.get("tags", [])
                updates["tags"] = _ensure_tag(existing_tags, APPOINTMENT_CONFIRMED_TAG)
                updates["is_high_intent"] = True

            if needs_manual_callback_flag:
                updates["needs_manual_callback"] = True
                existing_tags = updates.get("tags") or existing_lead.get("tags", [])
                updates["tags"] = _ensure_tag(existing_tags, MANUAL_CALLBACK_TAG)
                updates["is_high_intent"] = True

            if summary_text:
                updates["summary"] = summary_text
            if en_summary_text:
                updates["en_summary"] = en_summary_text

            current_chat_id = existing_lead.get("chat_id") or existing_lead.get("conversation_id")
            if current_chat_id != conversation_id:
                updates["chat_id"] = conversation_id

            if source_channel and existing_lead.get("source") != source_channel:
                updates["source"] = source_channel

            if updates:
                await db.leads.update_one({"_id": existing_lead["_id"]}, {"$set": updates})

        if (
            info_complete
            and not previous_info_complete
            and has_appointment_flag
            and previous_has_state != APPOINTMENT_STATE_OPEN_DAY
        ):
            logger.info("会话 %s 家长画像已完整，可推进开放日转化", conversation.id)

    except Exception as exc:
        logger.error("会话 %s 后处理失败: %s", conversation_id, exc, exc_info=True)

def _build_appointment_doc(payload: dict, merged_info: Optional[dict], user_id: str) -> Optional[dict]:
    campus = _normalize_campus(payload.get("campus") or (merged_info or {}).get("campus"))
    timeslot = payload.get("timeslot")
    if not timeslot:
        return None
    normalized_phone = _normalize_phone_value(payload.get("phone") or (merged_info or {}).get("phone"))
    created_at = datetime.utcnow()
    return {
        "campus": campus,
        "timeslot": timeslot.strip(),
        "status": "confirmed",
        "parent_name": _normalize_parent_name_candidate(payload.get("parent_name"))
        or _normalize_parent_name_candidate((merged_info or {}).get("parent_name")),
        "phone": normalized_phone,
        "note": payload.get("note"),
        "created_at": created_at,
        "updated_at": created_at,
        "created_by": user_id,
    }


# ========== API 路由 ==========

@router.get("/conversations", response_model=ConversationListResponse, summary="获取我的会话列表")
async def get_my_conversations(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=50, description="每页数量"),
    current_user: UserSchema = Depends(get_current_parent),
    db: PostgresCompatDatabase = Depends(get_database)
):
    """
    获取当前家长的会话列表
    
    - 支持状态筛选
    - 按更新时间倒序排列
    - 分页返回
    """
    # 构建查询条件
    query = {"parent_id": ObjectId(current_user.id)}

    # 计算总数
    total = await db.conversations.count_documents(query)
    
    # 分页查询
    skip = (page - 1) * page_size
    cursor = db.conversations.find(query).sort("updated_at", -1).skip(skip).limit(page_size)
    
    conversations = []
    async for conv_dict in cursor:
        # 转换 ObjectId 字段，确保响应可序列化
        conv_id = conv_dict.get("_id")
        if isinstance(conv_id, ObjectId):
            conv_id = str(conv_id)

        conversations.append({
            "id": conv_id,
            "message_count": conv_dict.get("message_count", 0),
            "last_message_at": conv_dict.get("last_message_at"),
            "created_at": conv_dict["created_at"],
            "updated_at": conv_dict["updated_at"]
        })

    return ConversationListResponse(
        total=total,
        items=conversations,
        page=page,
        page_size=page_size
    )


@router.post("/conversations", response_model=ConversationDetailResponse, summary="创建新会话")
async def create_conversation(
    request_data: CreateConversationRequest, # 使用请求体模型
    current_user: UserSchema = Depends(get_current_parent),
    db: PostgresCompatDatabase = Depends(get_database)
):
    """
    创建新的咨询会话
    
    - 状态初始为 active
    """
    parent_id = current_user.id
    
    now = datetime.utcnow()
    parent_object_id = ObjectId(parent_id)
    channel_source = normalize_channel_source(request_data.source)
    assistant = await _load_assistant(db, request_data.assistant_id)
    if request_data.assistant_id and not assistant:
        raise HTTPException(status_code=404, detail="助手不存在")
    if assistant and not assistant.get("is_active", True):
        raise HTTPException(status_code=400, detail="助手未启用")
    effective_school_id = request_data.school_id or (assistant.get("school_id") if assistant else None)

    conversation_data = {
        "parent_id": parent_object_id,
        "message_count": 0,
        "created_at": now,
        "updated_at": now,
        "last_message_at": None,
        "appointment": None,
        "school_id": effective_school_id,
        "assistant_id": assistant.get("id") if assistant else request_data.assistant_id,
        "ai_reply_enabled": True,
    }
    if channel_source:
        conversation_data["source_channel"] = channel_source
    
    result = await db.conversations.insert_one(conversation_data)
    inserted_id = result.inserted_id
    conversation_id_str = str(inserted_id)

    # 插入默认欢迎语作为系统首条消息（根据用户选择的语言）
    welcome_text = await _load_welcome_message(db, request_data.language, effective_school_id)
    welcome_message = MessageSchema(
        conversation_id=conversation_id_str,
        sender_type="bot",
        sender_name=str(assistant.get("name") or "助手") if assistant else "助手",
        content=welcome_text,
        metadata={"assistant_id": assistant.get("id")} if assistant else None,
    )
    welcome_msg_dict = welcome_message.model_dump()
    welcome_result = await db.messages.insert_one(welcome_msg_dict)
    welcome_message.id = str(welcome_result.inserted_id)

    welcome_time = welcome_message.created_at
    await db.conversations.update_one(
        {"_id": inserted_id},
        {
            "$set": {
                "message_count": 1,
                "last_message_at": welcome_time,
                "updated_at": welcome_time,
            }
        },
    )

    # 初始化会话画像缓存（用于跨轮保存已收集信息）
    await _save_conversation_profile(db, inserted_id, {}, {})

    # 从数据库中获取新创建的会话的完整文档
    new_conv_doc = await db.conversations.find_one({"_id": inserted_id})
    if not new_conv_doc:
        raise HTTPException(status_code=500, detail="Failed to create conversation")

    # 在验证前手动将 ObjectId 转换为字符串
    new_conv_doc["_id"] = str(new_conv_doc["_id"])
    new_conv_doc["parent_id"] = str(new_conv_doc["parent_id"])

    # 使用 model_validate 从文档创建模型实例
    conversation = ConversationSchema.model_validate(new_conv_doc)

    logger.info(f"家长 {current_user.phone} 创建新会话: {conversation.id}")
    
    return ConversationDetailResponse(
        id=conversation.id,
        message_count=conversation.message_count,
        last_message_at=conversation.last_message_at,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        school_id=conversation.school_id,
        assistant_id=conversation.assistant_id,
        ai_reply_enabled=bool(getattr(conversation, "ai_reply_enabled", True)),
        appointment=conversation.appointment.model_dump() if conversation.appointment else None,
    )


@router.get(
    "/conversations/{conversation_id}/welcome-message",
    response_model=WelcomeMessageTextResponse,
    summary="获取当前语言的首句欢迎语",
)
async def get_conversation_welcome_message(
    conversation_id: str,
    language: str = Query("zh-CN", description="语言代码"),
    school_id: str | None = Query(None, description="学校ID，用于旧会话兜底欢迎语作用域"),
    current_user: UserSchema = Depends(get_current_parent),
    db: PostgresCompatDatabase = Depends(get_database),
):
    """返回当前会话在指定语言下应显示的欢迎语。"""
    try:
        conv_id = ObjectId(conversation_id)
    except Exception:
        raise HTTPException(status_code=400, detail="无效的会话 ID")

    conv_dict = await db.conversations.find_one({
        "_id": conv_id,
        "parent_id": ObjectId(current_user.id),
    })
    if not conv_dict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在",
        )

    effective_school_id, _assistant, inferred_from_assistant = await _resolve_conversation_school_scope(
        db,
        conversation=conv_dict,
        fallback_school_id=school_id,
    )
    if inferred_from_assistant or (school_id and not conv_dict.get("school_id")):
        next_school_id = effective_school_id
        await db.conversations.update_one(
            {"_id": conv_id},
            {
                "$set": {
                    "school_id": next_school_id,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

    content = await _load_welcome_message(
        db,
        language=language,
        school_id=effective_school_id,
    )
    return WelcomeMessageTextResponse(language=language, content=content)


@router.get("/assistants", response_model=ParentAssistantListResponse, summary="获取当前学校可用助手")
async def list_parent_assistants(
    school_id: str | None = Query(None, description="学校ID"),
    conversation_id: str | None = Query(None, description="会话ID，用于推断当前已绑定助手"),
    current_user: UserSchema = Depends(get_current_parent),
    db: PostgresCompatDatabase = Depends(get_database),
):
    scope_school_id = (school_id or "").strip() or None
    selected_assistant_id: str | None = None

    if conversation_id:
        try:
            conv_id = ObjectId(conversation_id)
        except Exception:
            raise HTTPException(status_code=400, detail="无效的会话 ID")
        conv_dict = await db.conversations.find_one({
            "_id": conv_id,
            "parent_id": ObjectId(current_user.id),
        })
        if not conv_dict:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
        scope_school_id, _assistant, inferred_from_assistant = await _resolve_conversation_school_scope(
            db,
            conversation=conv_dict,
            fallback_school_id=scope_school_id,
        )
        if inferred_from_assistant and scope_school_id:
            await db.conversations.update_one(
                {"_id": conv_id},
                {"$set": {"school_id": scope_school_id, "updated_at": datetime.utcnow()}},
            )
        selected_assistant_id = (conv_dict.get("assistant_id") or "").strip() or None

    assistants = await AssistantService(db).list_assistants(school_id=scope_school_id)
    active_items = [item for item in assistants if item.get("is_active", True)]
    inferred_school_id = scope_school_id
    if not inferred_school_id:
        school_ids = {str(item.get("school_id") or "").strip() for item in active_items if str(item.get("school_id") or "").strip()}
        if len(school_ids) == 1:
            inferred_school_id = next(iter(school_ids))
    return ParentAssistantListResponse(
        items=active_items,
        selected_assistant_id=selected_assistant_id,
        school_id=inferred_school_id,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse, summary="获取会话详情")
async def get_conversation_detail(
    conversation_id: str,
    current_user: UserSchema = Depends(get_current_parent),
    db: PostgresCompatDatabase = Depends(get_database)
):
    """
    获取指定会话的详情
    
    - 只能查看自己的会话
    """
    try:
        conv_id = ObjectId(conversation_id)
    except Exception:
        raise HTTPException(status_code=400, detail="无效的会话 ID")

    # 查找会话
    conv_dict = await db.conversations.find_one({
        "_id": conv_id,
        "parent_id": ObjectId(current_user.id)  # 确保只能查看自己的会话
    })
    
    if not conv_dict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )
    
    # 在验证前手动将 ObjectId 转换为字符串并构建响应
    appointment = conv_dict.get("appointment")
    if appointment and isinstance(appointment, dict):
        appointment_payload = {
            key: value for key, value in appointment.items()
        }
    else:
        appointment_payload = None

    return ConversationDetailResponse(
        id=str(conv_dict["_id"]),
        message_count=conv_dict.get("message_count", 0),
        last_message_at=conv_dict.get("last_message_at"),
        created_at=conv_dict["created_at"],
        updated_at=conv_dict["updated_at"],
        school_id=conv_dict.get("school_id"),
        assistant_id=conv_dict.get("assistant_id"),
        ai_reply_enabled=bool(conv_dict.get("ai_reply_enabled", True)),
        appointment=appointment_payload
    )


@router.patch("/conversations/{conversation_id}/assistant", response_model=ConversationDetailResponse, summary="切换当前会话助手")
async def update_conversation_assistant(
    conversation_id: str,
    payload: UpdateConversationAssistantRequest,
    current_user: UserSchema = Depends(get_current_parent),
    db: PostgresCompatDatabase = Depends(get_database),
):
    try:
        conv_id = ObjectId(conversation_id)
    except Exception:
        raise HTTPException(status_code=400, detail="无效的会话 ID")

    conv_dict = await db.conversations.find_one({
        "_id": conv_id,
        "parent_id": ObjectId(current_user.id),
    })
    if not conv_dict:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")

    assistant_id = payload.assistant_id.strip()
    if not assistant_id:
        raise HTTPException(status_code=400, detail="assistant_id 不能为空")

    assistant = await _load_assistant(db, assistant_id)
    if not assistant:
        raise HTTPException(status_code=404, detail="助手不存在")
    if not assistant.get("is_active", True):
        raise HTTPException(status_code=400, detail="助手未启用")

    assistant_school_id = (assistant.get("school_id") or "").strip() or None
    conversation_school_id = (conv_dict.get("school_id") or "").strip() or None
    if conversation_school_id and assistant_school_id and conversation_school_id != assistant_school_id:
        raise HTTPException(status_code=400, detail="助手不属于当前会话所在学校")

    now = datetime.utcnow()
    updated_school_id = conversation_school_id or assistant_school_id
    await db.conversations.update_one(
        {"_id": conv_id},
        {
            "$set": {
                "assistant_id": assistant_id,
                "school_id": updated_school_id,
                "updated_at": now,
            }
        },
    )

    refreshed = await db.conversations.find_one({"_id": conv_id})
    if not refreshed:
        raise HTTPException(status_code=500, detail="更新会话助手失败")

    appointment = refreshed.get("appointment")
    appointment_payload = dict(appointment) if isinstance(appointment, dict) else None
    return ConversationDetailResponse(
        id=str(refreshed["_id"]),
        message_count=refreshed.get("message_count", 0),
        last_message_at=refreshed.get("last_message_at"),
        created_at=refreshed["created_at"],
        updated_at=refreshed["updated_at"],
        school_id=refreshed.get("school_id"),
        assistant_id=refreshed.get("assistant_id"),
        ai_reply_enabled=bool(refreshed.get("ai_reply_enabled", True)),
        appointment=appointment_payload,
    )


@router.get("/conversations/{conversation_id}/messages", response_model=MessageListResponse, summary="获取会话消息")
async def get_conversation_messages(
    conversation_id: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    language: str = Query("zh-CN", description="语言代码"),
    school_id: str | None = Query(None, description="学校ID，用于旧会话兜底欢迎语作用域"),
    current_user: UserSchema = Depends(get_current_parent),
    db: PostgresCompatDatabase = Depends(get_database)
):
    """
    获取指定会话的消息列表
    
    - 只能查看自己的会话消息
    - 按时间正序排列（最早的在前）
    - 分页返回
    """
    try:
        conv_id = ObjectId(conversation_id)
    except Exception:
        raise HTTPException(status_code=400, detail="无效的会话 ID")

    # 先检查会话是否存在且属于当前用户
    conv_dict = await db.conversations.find_one({
        "_id": conv_id,
        "parent_id": ObjectId(current_user.id)
    })
    
    if not conv_dict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )

    effective_school_id, _assistant, inferred_from_assistant = await _resolve_conversation_school_scope(
        db,
        conversation=conv_dict,
        fallback_school_id=school_id,
    )
    if inferred_from_assistant or (school_id and not conv_dict.get("school_id")):
        next_school_id = effective_school_id
        await db.conversations.update_one(
            {"_id": conv_id},
            {
                "$set": {
                    "school_id": next_school_id,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

    localized_welcome = await _load_welcome_message(
        db,
        language=language,
        school_id=effective_school_id,
    )
    
    # 查询消息
    query = {"conversation_id": conversation_id}
    total = await db.messages.count_documents(query)
    
    skip = (page - 1) * page_size
    cursor = (
        db.messages.find(query)
        .sort("_id", 1)
        .skip(skip)
        .limit(page_size)
    )
    
    messages = []
    should_replace_welcome = skip == 0
    welcome_replaced = False
    async for msg_dict in cursor:
        content = msg_dict["content"]
        if should_replace_welcome and not welcome_replaced and msg_dict.get("sender_type") == "bot":
            content = localized_welcome
            welcome_replaced = True
        messages.append({
            "id": str(msg_dict["_id"]),
            "conversation_id": msg_dict["conversation_id"],
            "sender_type": msg_dict["sender_type"],
            "sender_id": msg_dict.get("sender_id"),
            "sender_name": msg_dict.get("sender_name"),
            "content": content,
            "created_at": msg_dict["created_at"]
        })
    
    return MessageListResponse(
        total=total,
        items=messages,
        page=page,
        page_size=page_size,
        conversation={
            "id": str(conv_dict["_id"]),
            "message_count": conv_dict.get("message_count", 0),
            "last_message_at": conv_dict.get("last_message_at"),
        }
    )


@router.post("/conversations/{conversation_id}/messages", summary="发送消息（流式）")
async def send_message(
    conversation_id: str,
    request: SendMessageRequest,
    current_user: UserSchema = Depends(get_current_parent),
    db: PostgresCompatDatabase = Depends(get_database),
    ai_service: LangchainService = Depends(get_langchain_service)
):
    """
    在指定会话中发送消息
    
    流程：
    1. 保存用户消息
    2. 调用 LangChain 流式模型生成回复
    3. 保存 AI 回复
    4. 汇总对话并提取结构化信息
    5. 更新会话和线索数据
    """
    # 检查会话是否存在且属于当前用户
    try:
        conv_id = ObjectId(conversation_id)
    except Exception:
        raise HTTPException(status_code=400, detail="无效的会话 ID")

    conv_dict = await db.conversations.find_one({
        "_id": conv_id,
        "parent_id": ObjectId(current_user.id)
    })
    
    if not conv_dict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )

    conversation_school_id = conv_dict.get("school_id")
    conversation_assistant_id = (conv_dict.get("assistant_id") or "").strip() or None
    ai_reply_enabled = bool(conv_dict.get("ai_reply_enabled", True))
    request_assistant_id = (request.assistant_id or "").strip() or None
    effective_assistant_id = conversation_assistant_id or request_assistant_id
    assistant = await _load_assistant(db, effective_assistant_id)
    if effective_assistant_id and not assistant:
        raise HTTPException(status_code=404, detail="助手不存在")
    if request_assistant_id and not conv_dict.get("assistant_id"):
        updated_at = datetime.utcnow()
        next_school_id = (assistant.get("school_id") if assistant else None) or conv_dict.get("school_id")
        await db.conversations.update_one(
            {"_id": conv_id},
            {
                "$set": {
                    "assistant_id": request_assistant_id,
                    "school_id": next_school_id,
                    "updated_at": updated_at,
                }
            },
        )
        conv_dict["assistant_id"] = request_assistant_id
        conv_dict["school_id"] = next_school_id
        conv_dict["updated_at"] = updated_at
        effective_assistant_id = request_assistant_id
        conversation_assistant_id = request_assistant_id
    assistant_knowledge_base_ids: list[str] = []
    if assistant:
        raw_knowledge_base_ids = assistant.get("knowledge_base_ids")
        if isinstance(raw_knowledge_base_ids, list):
            assistant_knowledge_base_ids = [
                str(item).strip()
                for item in raw_knowledge_base_ids
                if str(item).strip()
            ]
        if not assistant_knowledge_base_ids:
            legacy_knowledge_base_id = str(assistant.get("knowledge_base_id") or "").strip()
            if legacy_knowledge_base_id:
                assistant_knowledge_base_ids = [legacy_knowledge_base_id]
    request_school_id = (request.school_id or "").strip() or None
    effective_school_id = (
        conversation_school_id
        or request_school_id
        or (assistant.get("school_id") if assistant else None)
        or DEFAULT_WELCOME_SCOPE
    )
    used_default_school_scope = not (conversation_school_id or request_school_id or (assistant.get("school_id") if assistant else None))
    if request_school_id and not conv_dict.get("school_id"):
        updated_at = datetime.utcnow()
        await db.conversations.update_one(
            {"_id": conv_id},
            {
                "$set": {
                    "school_id": request_school_id,
                    "updated_at": updated_at,
                }
            },
        )
        conv_dict["school_id"] = request_school_id
        conv_dict["updated_at"] = updated_at
        logger.info("旧会话 %s 已补写 school_id=%s", conversation_id, request_school_id)
    elif used_default_school_scope:
        logger.info(
            "会话 %s 未提供 school_id，知识库作用域回落到默认学校 %s",
            conversation_id,
            DEFAULT_WELCOME_SCOPE,
        )
    
    # 在验证前手动将 ObjectId 转换为字符串
    conv_dict["_id"] = str(conv_dict["_id"])
    conv_dict["parent_id"] = str(conv_dict["parent_id"])
    conversation = ConversationSchema.model_validate(conv_dict)
    
    # 1. 保存用户消息
    user_message = MessageSchema(
        conversation_id=conversation.id, # 使用验证过的模型ID
        sender_type="parent",
        sender_id=current_user.id,
        sender_name=current_user.name,
        content=request.content
    )
    
    user_msg_dict = user_message.model_dump()
    result = await db.messages.insert_one(user_msg_dict)
    user_message.id = str(result.inserted_id)  # 设置生成的 ID

    logger.info(f"家长 {current_user.phone} 在会话 {conversation_id} 发送消息")

    # 先行刷新消息计数，确保即便后续生成失败也能保持准确
    current_time = user_message.created_at
    user_message_total = await db.messages.count_documents({"conversation_id": conversation.id})
    await db.conversations.update_one(
        {"_id": conv_id},
        {
            "$set": {
                "message_count": user_message_total,
                "last_message_at": current_time,
                "updated_at": current_time,
            }
        },
    )

    profile_doc = await _load_conversation_profile(db, conv_id)
    profile_info = dict(profile_doc.get("info", {}) or {})
    profile_flags = dict(profile_doc.get("flags", {}) or {})
    if "has_appointment" in profile_info:
        profile_info["has_appointment"] = _normalize_has_appointment(profile_info.get("has_appointment"))
    prev_info_complete = _has_complete_profile(profile_info)

    # 获取历史消息（不包含当前这一条）用于提示模型保留上下文
    history: list[dict] = []
    history_cursor = (
        db.messages.find(
            {
                "conversation_id": conversation.id,
                "_id": {"$lt": user_message.id},
            }
        )
        .sort("_id", 1)
    )
    async for msg_doc in history_cursor:
        if not _should_include_message_in_assistant_history(msg_doc, effective_assistant_id):
            continue
        sender_type = msg_doc.get("sender_type")
        if sender_type == "parent":
            role = "user"
        else:
            role = "assistant"
        history.append({"role": role, "content": msg_doc.get("content", "")})
    # 仅保留近期消息以控制上下文长度
    if len(history) > 20:
        history = history[-20:]
    
    # 2. 创建流式生成器
    manual_callback_triggered = False

    async def generate_stream() -> AsyncGenerator[str, None]:
        """生成流式响应数据"""
        nonlocal profile_info, profile_flags, prev_info_complete, manual_callback_triggered
        full_answer = ""  # 累积完整答案
        
        try:
            latest_conversation = await db.conversations.find_one(
                {"_id": conv_id},
                {"ai_reply_enabled": 1, "ai_reply_auto_resume_pending": 1, "ai_reply_disabled_at": 1, "_id": 1},
            )
            latest_conversation = await _ensure_ai_reply_auto_resumed(db, latest_conversation)
            latest_ai_reply_enabled = bool(
                latest_conversation.get("ai_reply_enabled", ai_reply_enabled)
            ) if latest_conversation else ai_reply_enabled
            if not latest_ai_reply_enabled:
                yield f"data: {json.dumps({'event': 'ai_disabled'})}\n\n"
                return

            logger.debug("%s", "=" * 80)
            logger.debug("开始流式调用 LangChain 模型")
            logger.debug("query = %s", request.content)
            logger.debug("user_id = %s", current_user.id)
            logger.debug("%s", "=" * 80)

            retrieved_docs = []
            try:
                retrieved_docs = rag_search.search(
                    request.content,
                    top_k=settings.CHROMA_TOP_K,
                    school_key=effective_school_id,
                    knowledge_base_ids=assistant_knowledge_base_ids or None,
                )
                logger.info(
                    "知识库检索完成: conversation=%s effective_school_id=%s hits=%d query=%s",
                    conversation_id,
                    effective_school_id,
                    len(retrieved_docs),
                    request.content,
                )
                retrieved_docs = await filter_live_rag_results(
                    db,
                    school_id=effective_school_id,
                    items=retrieved_docs,
                    knowledge_base_ids=assistant_knowledge_base_ids or None,
                )
                logger.info(
                    "知识库活数据过滤完成: conversation=%s effective_school_id=%s live_hits=%d query=%s",
                    conversation_id,
                    effective_school_id,
                    len(retrieved_docs),
                    request.content,
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("知识库检索失败（手工回访检测）：%s", exc)
            manual_reason = await _maybe_record_manual_callback(
                db,
                conversation.id,
                current_user,
                request.content,
                retrieved_docs,
                history=history,
                profile_info=profile_info,
            )
            if manual_reason:
                manual_callback_triggered = True
                profile_flags[MANUAL_CALLBACK_FLAG] = True

            latest_invalid_contact_fields = _detect_invalid_contact_fields(request.content)
            runtime_instructions: list[str] = []
            if latest_invalid_contact_fields:
                runtime_instructions.append(
                    _invalid_contact_runtime_instruction_for(request.language, latest_invalid_contact_fields)
                )

            async for token in ai_service.stream_chat_reply(
                query=request.content,
                user_id=current_user.id,
                history=history,
                documents=retrieved_docs,
                school_id=effective_school_id,
                assistant_id=effective_assistant_id,
                knowledge_base_ids=assistant_knowledge_base_ids or None,
                locale=request.language,
                runtime_instructions=runtime_instructions,
            ):
                if not token:
                    continue
                full_answer += token
                yield f"data: {json.dumps({'answer': token})}\n\n"

            logger.debug("流式调用完成，full_answer = %s", full_answer)

            parsed_answer = full_answer.strip()

            # 3. 保存完整的 AI 回复
            if parsed_answer:
                bot_message = MessageSchema(
                    conversation_id=conversation.id,
                    sender_type="bot",
                    content=parsed_answer,
                    metadata={"assistant_id": effective_assistant_id} if effective_assistant_id else None,
                )

                bot_msg_dict = bot_message.model_dump()
                result = await db.messages.insert_one(bot_msg_dict)
                bot_message.id = str(result.inserted_id)

                quick_transcript = _build_transcript_from_history(history, request.content, parsed_answer)
                quick_profile_info = _fallback_extract_info(dict(profile_info), quick_transcript)
                quick_profile_info, _ = _sanitize_contact_fields(quick_profile_info)
                if manual_callback_triggered or _needs_manual_callback(quick_profile_info):
                    profile_flags[MANUAL_CALLBACK_FLAG] = True
                bot_message_count_delta = 1
                current_time = datetime.utcnow()
                await db.conversations.update_one(
                    {"_id": conv_id},
                    {
                        "$set": {
                            "message_count": user_message_total + bot_message_count_delta,
                            "last_message_at": current_time,
                            "updated_at": current_time,
                        }
                    },
                )

                yield f"data: {json.dumps({'event': 'done', 'bot_message': {'id': str(bot_message.id), 'content': parsed_answer}})}\n\n"

                asyncio.create_task(
                    _postprocess_parent_reply(
                        db=db,
                        ai_service=ai_service,
                        conversation=conversation,
                        conversation_id=conversation_id,
                        conv_id=conv_id,
                        conv_snapshot=dict(conv_dict),
                        current_user=current_user,
                        locale=request.language,
                        profile_info=quick_profile_info,
                        profile_flags=dict(profile_flags),
                        prev_info_complete=prev_info_complete,
                        manual_callback_triggered=manual_callback_triggered,
                    )
                )
                
        except Exception as e:
            logger.error(f"流式处理异常: {type(e).__name__}: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    # 返回流式响应
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/me", summary="获取我的个人信息")
async def get_my_profile(
    current_user: UserSchema = Depends(get_current_parent),
):
    """
    获取当前家长的个人信息
    """
    return {
        "id": current_user.id,
        "phone": current_user.phone,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at.isoformat()
    }
