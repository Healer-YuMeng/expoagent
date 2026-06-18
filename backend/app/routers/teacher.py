"""
老师端路由
处理招生老师相关的工作台、线索等接口
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from bson import ObjectId

from app.db import PostgresCompatDatabase, get_database
from app.models.user import UserSchema
# We will create this dependency next
from app.core.dependencies import get_current_teacher 
from app.routers.parent import (
    DEFAULT_WELCOME_MESSAGES,
    MANUAL_CALLBACK_COLLECTION,
    SYSTEM_SETTINGS_COLLECTION,
    WELCOME_MESSAGE_KEY,
)
from app.services.langchain_service import get_langchain_service
from app.services.channel_metrics import get_channel_stats, CHANNEL_CONFIG
from app.routers.utils import build_lead_chat_lookup

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/teacher", tags=["老师端"])
HIDDEN_TEACHER_MESSAGE_TAGS = {"manual_callback_prompt"}
WELCOME_MESSAGE_TRANSLATION_TARGETS = {
    "en": "English",
    "zh-TW": "Traditional Chinese (繁體中文)",
    "ja": "Japanese (日本語)",
    "ko": "Korean (한국어)",
    "fr": "French (Français)",
    "es": "Spanish (Español)",
    "ru": "Russian (Русский)",
}


class WelcomeMessageResponse(BaseModel):
    messages: dict[str, str] = Field(
        ..., 
        description="多语言欢迎语，key为语言代码(en/zh-CN/zh-TW/ja/ko/fr/es/ru)，value为欢迎语内容"
    )


class UpdateWelcomeMessageRequest(BaseModel):
    messages: dict[str, str] = Field(
        ..., 
        description="多语言欢迎语，key为语言代码，value为欢迎语内容"
    )


class TranslateWelcomeMessageRequest(BaseModel):
    source_text: str = Field(..., min_length=1, description="源文本")
    source_lang: str = Field(default="zh-CN", description="源语言代码")


class TranslateWelcomeMessageResponse(BaseModel):
    translations: dict[str, str] = Field(..., description="翻译结果")
    failed_languages: list[str] = Field(default_factory=list, description="翻译失败的语言代码")


class ManualCallbackItem(BaseModel):
    conversation_id: str
    reason: str
    query: str
    parent_name: str | None = None
    parent_phone: str | None = None
    created_at: datetime
    updated_at: datetime


class ManualCallbackListResponse(BaseModel):
    items: List[ManualCallbackItem]


class ConversationMessage(BaseModel):
    id: str
    conversation_id: str
    sender_type: str
    sender_name: str | None = None
    content: str
    created_at: datetime | None = None


class ConversationMessagesResponse(BaseModel):
    total: int
    items: List[ConversationMessage]


def _normalize_welcome_messages(value: Any) -> dict[str, str]:
    if isinstance(value, str):
        text = value.strip()
        return {"zh-CN": text} if text else {}

    if not isinstance(value, dict):
        return {}

    messages: dict[str, str] = {}
    for lang, text in value.items():
        if not isinstance(lang, str) or not isinstance(text, str):
            continue
        stripped = text.strip()
        if stripped:
            messages[lang] = stripped
    return messages


def _looks_incomplete_translation(source_text: str, translated_text: str | None) -> bool:
    if not translated_text:
        return True

    source = source_text.strip()
    translated = translated_text.strip()
    if not translated:
        return True
    if translated == source:
        return True

    if len(source) >= 40 and len(translated) < 20:
        return True
    return False


async def _translate_single_welcome_message(
    *,
    langchain_service,
    source_text: str,
    source_lang: str,
    target_lang: str,
    target_name: str,
) -> tuple[str, str | None]:
    system_prompt = (
        "你是一位专业的翻译专家，精通多国语言，尤其擅长教育领域的翻译。"
        "请保持译文的专业性、准确性和自然性，确保符合目标语言的表达习惯。"
    )
    user_prompt = f"""请将以下{source_lang}文本翻译成 {target_name}：

{source_text}

翻译要求：
1. 保持原文的专业性和友好语气。
2. 适应目标语言的文化习惯。
3. 保留换行格式。
4. 确保学校名称、校区名称等专有名词的准确性。
5. 只返回翻译结果，不要添加任何解释。"""

    translated_text = await langchain_service.complete_text(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0,
        max_tokens=1024,
    )
    if _looks_incomplete_translation(source_text, translated_text):
        return target_lang, None
    return target_lang, translated_text.strip()


def _should_hide_teacher_message(message_doc: dict) -> bool:
    metadata = message_doc.get("metadata") or {}
    if not isinstance(metadata, dict):
        return False
    system_tag = metadata.get("system_tag")
    return system_tag in HIDDEN_TEACHER_MESSAGE_TAGS

@router.get("/dashboard", summary="获取老师工作台摘要数据")
async def get_teacher_dashboard(
    current_user: UserSchema = Depends(get_current_teacher),
    db: PostgresCompatDatabase = Depends(get_database)
):
    """
    获取老师工作台的核心摘要数据：
    - 今日咨询量
    - 总线索数
    - 高意向线索数
    - 待确认预约数
    """
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    # 1. 今日咨询量 (今日创建的会话数)
    today_consultations = await db.conversations.count_documents({
        "created_at": {"$gte": today_start, "$lt": today_end}
    })

    # 2. 总线索数
    valid_leads = await db.leads.count_documents({})

    # 3. 高意向线索数
    urgent_followups = await db.leads.count_documents({
        "is_high_intent": True
    })

    pending_appointments = await db.leads.count_documents({
        "appointment.status": "pending"
    })

    manual_callbacks = await db.leads.count_documents({
        "needs_manual_callback": True
    })

    now = datetime.utcnow()
    date_keys = {
        "daily": now.strftime("%Y-%m-%d"),
        "monthly": now.strftime("%Y-%m"),
        "yearly": now.strftime("%Y"),
    }
    source_stats: dict[str, list[dict[str, object]]] = {}
    for period, date_key in date_keys.items():
        stats_map = await get_channel_stats(db, period, date_key)
        source_stats[period] = [
            {
                "channel": slug,
                "label": CHANNEL_CONFIG[slug],
                "visits": values["visits"],
                "appointments": values["appointments"],
            }
            for slug, values in stats_map.items()
        ]

    return {
        "today_consultations": today_consultations,
        "valid_leads": valid_leads,
        "urgent_followups": urgent_followups,
        "pending_appointments": pending_appointments,
        "manual_callbacks": manual_callbacks,
        "source_stats": source_stats,
    }


@router.get(
    "/settings/welcome-message",
    response_model=WelcomeMessageResponse,
    summary="获取 AI 欢迎语配置（多语言）",
)
async def get_welcome_message_setting(
    current_user: UserSchema = Depends(get_current_teacher),
    db: PostgresCompatDatabase = Depends(get_database),
) -> WelcomeMessageResponse:
    scope_school = current_user.school_id if current_user.role == "school_admin" else None
    doc = await db[SYSTEM_SETTINGS_COLLECTION].find_one({"_id": _welcome_key(scope_school)})
    if not doc and scope_school:
        doc = await db[SYSTEM_SETTINGS_COLLECTION].find_one({"_id": _welcome_key(None)})
    if doc:
        messages = _normalize_welcome_messages(doc.get("value"))
        if messages:
            return WelcomeMessageResponse(messages=messages)

    return WelcomeMessageResponse(messages=DEFAULT_WELCOME_MESSAGES.copy())


@router.put(
    "/settings/welcome-message",
    response_model=WelcomeMessageResponse,
    summary="更新 AI 欢迎语配置（多语言）",
)
async def update_welcome_message_setting(
    request: UpdateWelcomeMessageRequest,
    current_user: UserSchema = Depends(get_current_teacher),
    db: PostgresCompatDatabase = Depends(get_database),
) -> WelcomeMessageResponse:
    messages = _normalize_welcome_messages(request.messages)
    if not messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="至少需要提供一个语言的欢迎语"
        )

    now = datetime.utcnow()
    scope_school = current_user.school_id if current_user.role == "school_admin" else None
    await db[SYSTEM_SETTINGS_COLLECTION].update_one(
        {"_id": _welcome_key(scope_school)},
        {
            "$set": {
                "key": WELCOME_MESSAGE_KEY,
                "value": messages,
                "updated_at": now,
                "updated_by": current_user.id,
            },
            "$setOnInsert": {
                "created_at": now,
            },
        },
        upsert=True,
    )
    logger.info("Teacher %s 更新了欢迎语设置（%d个语言）", current_user.id, len(messages))
    return WelcomeMessageResponse(messages=messages)


@router.post(
    "/settings/welcome-message/translate",
    response_model=TranslateWelcomeMessageResponse,
    summary="AI自动翻译欢迎语到多种语言",
)
async def translate_welcome_message(
    request: TranslateWelcomeMessageRequest,
    current_user: UserSchema = Depends(get_current_teacher),
) -> TranslateWelcomeMessageResponse:
    """
    使用AI将源文本翻译成7种语言（保留源语言）
    """
    source_text = request.source_text.strip()
    langchain_service = get_langchain_service()
    translations = {request.source_lang: source_text}
    tasks = [
        _translate_single_welcome_message(
            langchain_service=langchain_service,
            source_text=source_text,
            source_lang=request.source_lang,
            target_lang=lang,
            target_name=name,
        )
        for lang, name in WELCOME_MESSAGE_TRANSLATION_TARGETS.items()
    ]
    failed_languages: list[str] = []
    target_langs = list(WELCOME_MESSAGE_TRANSLATION_TARGETS.keys())
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for lang_code, result in zip(target_langs, results):
        if isinstance(result, Exception):
            logger.error("欢迎语单语言翻译失败: %s", result)
            failed_languages.append(lang_code)
            continue
        _, translated_text = result
        if translated_text:
            translations[lang_code] = translated_text
        else:
            failed_languages.append(lang_code)

    translated_count = len([lang for lang in translations if lang != request.source_lang])
    if translated_count == 0:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI 翻译暂时不可用，请检查模型配置或稍后重试。",
        )

    logger.info(
        "Teacher %s 完成AI翻译，成功语言数=%d",
        current_user.id,
        translated_count,
    )
    return TranslateWelcomeMessageResponse(
        translations=translations,
        failed_languages=failed_languages,
    )


@router.get(
    "/manual-callbacks",
    response_model=ManualCallbackListResponse,
    summary="获取人工回访提醒列表",
)
async def get_manual_callbacks(
    current_user: UserSchema = Depends(get_current_teacher),
    db: PostgresCompatDatabase = Depends(get_database),
) -> ManualCallbackListResponse:
    cursor = (
        db[MANUAL_CALLBACK_COLLECTION]
        .find({"resolved": False})
        .sort("updated_at", -1)
    )
    items: list[ManualCallbackItem] = []
    async for doc in cursor:
        items.append(
            ManualCallbackItem(
                conversation_id=str(doc.get("conversation_id")),
                reason=doc.get("reason", ""),
                query=doc.get("query", ""),
                parent_name=doc.get("parent_name"),
                parent_phone=doc.get("parent_phone"),
                created_at=doc.get("created_at") or doc.get("updated_at") or datetime.utcnow(),
                updated_at=doc.get("updated_at") or datetime.utcnow(),
            )
        )
    return ManualCallbackListResponse(items=items)


@router.delete(
    "/manual-callbacks/{conversation_id}",
    summary="删除人工回访提醒",
)
async def delete_manual_callback(
    conversation_id: str,
    current_user: UserSchema = Depends(get_current_teacher),
    db: PostgresCompatDatabase = Depends(get_database),
):
    """
    删除人工回访提醒（从数据库中删除记录）
    同时同步更新关联的线索（leads）数据
    """
    # 1. 删除提醒记录
    result = await db[MANUAL_CALLBACK_COLLECTION].delete_one(
        {"conversation_id": conversation_id}
    )
    
    if result.deleted_count == 0:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="提醒不存在"
        )
    
    logger.info(f"教师 {current_user.phone} 删除回访提醒 {conversation_id}")
    
    # 2. 同步更新关联的线索：移除"需人工回访"标记
    try:
        # 查找该对话关联的线索
        lead = await db.leads.find_one(build_lead_chat_lookup(conversation_id))
        
        if lead:
            # 更新线索：移除人工回访标记和标签
            update_result = await db.leads.update_one(
                {"_id": lead["_id"]},
                {
                    "$set": {
                        "needs_manual_callback": False,
                        "updated_at": datetime.utcnow()
                    },
                    "$pull": {"tags": "需人工回访"}
                }
            )
            
            if update_result.modified_count > 0:
                logger.info(
                    f"已同步更新线索 {lead['_id']}，移除人工回访标记（关联会话: {conversation_id}）"
                )
            else:
                logger.warning(
                    f"线索 {lead['_id']} 更新失败或无需更新（关联会话: {conversation_id}）"
                )
        else:
            logger.info(f"未找到会话 {conversation_id} 关联的线索，无需同步更新")
    
    except Exception as e:
        # 记录错误但不影响删除操作的返回
        logger.error(f"同步更新线索时出错（会话 {conversation_id}）: {str(e)}")
    
    return {"message": "提醒已删除"}


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=ConversationMessagesResponse,
    summary="获取会话消息（老师端）",
)
async def get_conversation_messages(
    conversation_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=500),
    current_user: UserSchema = Depends(get_current_teacher),
    db: PostgresCompatDatabase = Depends(get_database),
) -> ConversationMessagesResponse:
    candidates: list = [conversation_id]
    if ObjectId.is_valid(conversation_id):
        candidates.append(ObjectId(conversation_id))

    conversation = await db.conversations.find_one({"_id": {"$in": candidates}})
    if not conversation:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="会话不存在")

    base_filter = {"conversation_id": {"$in": candidates}}
    visible_messages: list[ConversationMessage] = []
    cursor = db.messages.find(base_filter).sort("_id", 1)
    async for msg in cursor:
        if _should_hide_teacher_message(msg):
            continue
        msg_id = msg.get("_id")
        if isinstance(msg_id, ObjectId):
            msg_id = str(msg_id)
        visible_messages.append(
            ConversationMessage(
                id=str(msg_id),
                conversation_id=conversation_id,
                sender_type=msg.get("sender_type", "unknown"),
                sender_name=msg.get("sender_name"),
                content=msg.get("content", ""),
                created_at=msg.get("created_at"),
            )
        )

    total = len(visible_messages)
    skip = (page - 1) * page_size
    items = visible_messages[skip:skip + page_size]

    return ConversationMessagesResponse(total=total, items=items)
def _welcome_key(school_id: str | None) -> str:
    return f"{WELCOME_MESSAGE_KEY}:{school_id or 'global'}"
