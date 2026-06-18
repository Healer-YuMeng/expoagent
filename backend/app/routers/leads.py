"""
线索管理路由
处理线索的查询、更新、分配、跟进记录等操作
"""
import asyncio
import logging
import re
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo
from typing import Optional, List, Any, Literal
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.db import PostgresCompatDatabase, get_database
from app.models.user import UserSchema
from app.models.lead import LeadSchema, FollowUpNote
from app.core.dependencies import get_current_teacher
from app.services.langchain_service import get_langchain_service
from app.services.notification_service import send_sms
from bson import ObjectId

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/leads", tags=["线索管理"])

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
APPOINTMENT_PENDING_TAG = "预约待确认"
APPOINTMENT_CONFIRMED_TAG = "预约已确认"
APPOINTMENT_REJECTED_TAG = "预约需改约"
HIDDEN_LEAD_MESSAGE_TAGS = {"manual_callback_prompt"}
MAX_WECOM_HISTORY = 200
NO_SUMMARY_TEXT_ZH = "暂无有效信息"
NO_SUMMARY_TEXT_EN = "No valid summary yet"
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


def _to_shanghai_str(value: Any) -> Optional[str]:
    if not value:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            value = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return text
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=ZoneInfo("UTC"))
        return dt.astimezone(SHANGHAI_TZ).strftime("%Y/%m/%d %H:%M:%S")
    return None


# ========== 请求/响应模型 ==========

class FollowUpOwnerPayload(BaseModel):
    """跟进老师信息"""
    name: str = Field(..., description="老师姓名", min_length=1)
    campus: Optional[str] = Field(default=None, description="负责校区")
    wechat_id: Optional[str] = Field(default=None, description="企业微信 ID")
    qr_code_url: Optional[str] = Field(default=None, description="二维码链接")
    contact_phone: Optional[str] = Field(default=None, description="联系方式")

class LeadListResponse(BaseModel):
    """线索列表响应"""
    total: int
    items: List[dict]
    page: int
    page_size: int


class LeadDetailResponse(BaseModel):
    """线索详情响应"""
    id: str
    parent_id: str
    parent_name: str
    parent_phone: Optional[str]
    parent_email: Optional[str]
    display_name: Optional[str]
    display_phone: Optional[str]
    campus: Optional[str]
    extracted_info: dict[str, Any]
    student_name: Optional[str]
    student_age: Optional[int]
    student_grade: Optional[str]
    is_high_intent: bool
    needs_manual_callback: bool
    source: str
    intent_score: int
    summary: Optional[str] = None
    en_summary: Optional[str] = None
    conversation_id: Optional[str]
    chat_id: Optional[str] = None
    qv_chat_id: Optional[str] = None
    first_message_at: Optional[str] = None
    tags: List[str]
    notes: List[dict]
    next_follow_up_date: Optional[str]
    created_at: str
    updated_at: str
    appointment: Optional[dict] = None
    conversation_history: List[dict] = Field(default_factory=list, description="历史会话记录")
    follow_up_owner: Optional[dict] = Field(default=None, description="跟进老师信息")
    wecom_status: Literal["not_added", "pending", "added"] = "not_added"
    wecom_chat_history: List[dict] = Field(default_factory=list, description="企业微信聊天记录")
    wecom_contact_name: Optional[str] = None
    wecom_contact_id: Optional[str] = None


class CreateLeadRequest(BaseModel):
    """创建线索请求"""
    parent_phone: str = Field(..., pattern=r"^1[3-9]\d{9}$", description="家长手机号")
    parent_name: str = Field(..., min_length=1, description="家长姓名")
    parent_email: Optional[str] = None
    student_name: Optional[str] = None
    student_age: Optional[int] = Field(None, ge=0, le=18)
    student_grade: Optional[str] = None
    source: str = Field("manual", description="来源")
    is_high_intent: bool = Field(False, description="是否高意向")
    needs_manual_callback: bool = Field(False, description="是否需要人工电话回访")
    tags: Optional[List[str]] = None
    follow_up_owner: Optional[FollowUpOwnerPayload] = Field(default=None, description="跟进老师信息")
    wecom_contact_name: Optional[str] = Field(default=None, description="企业微信昵称")


class UpdateLeadRequest(BaseModel):
    """更新线索请求"""
    is_high_intent: Optional[bool] = Field(None, description="是否高意向")
    needs_manual_callback: Optional[bool] = Field(None, description="是否需要人工回访")
    student_name: Optional[str] = None
    student_age: Optional[int] = Field(None, ge=0, le=18)
    student_grade: Optional[str] = None
    parent_email: Optional[str] = None
    tags: Optional[List[str]] = None
    next_follow_up_date: Optional[datetime] = None
    wecom_status: Optional[Literal["not_added", "pending", "added"]] = Field(
        default=None,
        description="企微状态"
    )
    follow_up_owner: Optional[FollowUpOwnerPayload] = Field(default=None, description="跟进老师信息")
    wecom_contact_name: Optional[str] = Field(default=None, description="企业微信昵称")


class AddNoteRequest(BaseModel):
    """添加跟进记录请求"""
    content: str = Field(..., min_length=1, max_length=2000, description="跟进内容")
    follow_up_method: str = Field(..., description="跟进方式: phone/wechat/email/visit/other")


class UpdateNoteRequest(BaseModel):
    """更新跟进记录请求"""
    content: str = Field(..., min_length=1, max_length=2000, description="跟进内容")
    follow_up_method: Optional[str] = Field(default=None, description="跟进方式: phone/wechat/email/visit/other")


class AppointmentActionRequest(BaseModel):
    """预约确认/拒绝请求"""
    note: Optional[str] = Field(default=None, description="补充备注")


# ========== 工具函数 ========== 

def _id_filter(value: str) -> dict[str, Any]:
    return {"_id": ObjectId(value)} if ObjectId.is_valid(value) else {"_id": value}


def _to_shanghai_str(value: Any) -> Optional[str]:
    if not value:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            value = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return text
    if not isinstance(value, datetime):
        return None
    local_tz = ZoneInfo("Asia/Shanghai")
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo("UTC"))
    local_dt = value.astimezone(local_tz)
    return local_dt.strftime("%Y/%m/%d %H:%M:%S")


def _ensure_tag(tags: list[str], tag: str) -> list[str]:
    if tag not in tags:
        tags.append(tag)
    return tags


def _apply_appointment_tag(tags: list[str], status: str) -> list[str]:
    filtered = [t for t in tags if t not in {APPOINTMENT_PENDING_TAG, APPOINTMENT_CONFIRMED_TAG, APPOINTMENT_REJECTED_TAG}]
    if status == "pending":
        return _ensure_tag(filtered, APPOINTMENT_PENDING_TAG)
    if status == "confirmed":
        return _ensure_tag(filtered, APPOINTMENT_CONFIRMED_TAG)
    if status == "rejected":
        return _ensure_tag(filtered, APPOINTMENT_REJECTED_TAG)
    return filtered


def _should_hide_lead_conversation_message(message_doc: dict) -> bool:
    metadata = message_doc.get("metadata") or {}
    if not isinstance(metadata, dict):
        return False
    return metadata.get("system_tag") in HIDDEN_LEAD_MESSAGE_TAGS


def _resolve_lead_campus(lead_dict: Optional[dict]) -> Optional[str]:
    if not lead_dict:
        return None
    extracted_info = lead_dict.get("extracted_info") or {}
    if isinstance(extracted_info, dict) and extracted_info.get("campus"):
        return extracted_info.get("campus")
    return lead_dict.get("campus")


def _serialize_appointment(appointment: Optional[dict], fallback_campus: Optional[str] = None) -> Optional[dict]:
    if not appointment:
        return None
    data = dict(appointment)
    if not data.get("campus") and fallback_campus:
        data["campus"] = fallback_campus
    data["created_at"] = _to_shanghai_str(data.get("created_at"))
    data["updated_at"] = _to_shanghai_str(data.get("updated_at"))
    return data


def _serialize_wecom_messages(messages: Optional[List[dict]]) -> List[dict]:
    if not messages:
        return []
    serialized: List[dict] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        sent_at = msg.get("sent_at")
        serialized.append({
            "id": str(msg.get("id") or msg.get("_id") or ObjectId()),
            "external_userid": msg.get("external_userid"),
            "direction": msg.get("direction", "parent"),
            "content": msg.get("content", ""),
            "sent_at": _to_shanghai_str(sent_at) if sent_at else None,
        })
    return serialized


def _build_export_rows(items: List[dict]) -> list[dict]:
    rows: list[dict] = []
    for item in items:
        appointment = item.get("appointment") or {}
        rows.append(
            {
                "家长姓名": item.get("parent_name") or item.get("display_name") or "",
                "手机号": item.get("parent_phone") or item.get("display_phone") or "",
                "邮箱": item.get("parent_email") or "",
                "意向校区": item.get("campus") or "",
                "学生姓名": item.get("student_name") or "",
                "AI摘要": item.get("summary") or "",
                "高意向": "是" if item.get("is_high_intent") else "否",
                "需人工回访": "是" if item.get("needs_manual_callback") else "否",
                "企微状态": item.get("wecom_status") or "",
                "企微昵称": item.get("wecom_contact_name") or "",
                "预约状态": appointment.get("status") or "",
                "预约时间": appointment.get("timeslot") or "",
                "创建时间": item.get("created_at") or "",
                "更新时间": item.get("updated_at") or "",
                "来源": item.get("source") or "",
            }
        )
    return rows


def _prefers_english(language: Optional[str]) -> bool:
    return str(language or "").lower().startswith("en")


def _normalize_parent_name_candidate(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if candidate == "招生助手":
        return None
    if candidate == DEFAULT_PARENT_DISPLAY_NAME:
        return candidate
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


async def _ensure_english_summary(
    lead_dict: dict[str, Any],
    db: PostgresCompatDatabase,
) -> Optional[str]:
    existing = (lead_dict.get("en_summary") or "").strip()
    if existing:
        return existing

    summary = (lead_dict.get("summary") or "").strip()
    if not summary:
        lead_dict["en_summary"] = NO_SUMMARY_TEXT_EN
        await db.leads.update_one({"_id": lead_dict["_id"]}, {"$set": {"en_summary": NO_SUMMARY_TEXT_EN}})
        return NO_SUMMARY_TEXT_EN

    if summary == NO_SUMMARY_TEXT_ZH:
        lead_dict["en_summary"] = NO_SUMMARY_TEXT_EN
        await db.leads.update_one({"_id": lead_dict["_id"]}, {"$set": {"en_summary": NO_SUMMARY_TEXT_EN}})
        return NO_SUMMARY_TEXT_EN

    translated = await get_langchain_service().translate_summary_to_english(summary)
    resolved = translated.strip() if translated else summary
    lead_dict["en_summary"] = resolved
    await db.leads.update_one({"_id": lead_dict["_id"]}, {"$set": {"en_summary": resolved}})
    return resolved


# ========== API 路由 ========== 

@router.get("", response_model=LeadListResponse, summary="获取线索列表")
async def get_leads(
    high_intent_only: Optional[bool] = Query(None, description="是否仅查看高意向线索"),
    manual_callback_only: Optional[bool] = Query(None, description="是否仅查看需人工回访线索"),
    search: Optional[str] = Query(None, description="搜索（姓名/手机号）"),
    appointment_status: Optional[str] = Query(None, description="预约状态筛选：pending/confirmed/rejected"),
    wecom_status: Optional[Literal["not_added", "pending", "added"]] = Query(
        None,
        description="企微添加状态筛选"
    ),
    language: Optional[str] = Query(None, description="当前界面语言"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_teacher: UserSchema = Depends(get_current_teacher),
    db: PostgresCompatDatabase = Depends(get_database)
):
    """
    获取线索列表（教师）
    
    - 支持多维度筛选
    - 支持搜索
    - 按人工回访、高意向标记和创建时间排序
    """
    query: dict[str, Any] = {}
    # 学校隔离：school_admin 按自身学校，teacher 按其 admin 对应学校，super_admin 不过滤
    school_scope = None
    if current_teacher.role == "school_admin":
        school_scope = current_teacher.school_id
    elif current_teacher.role == "teacher" and current_teacher.admin_id:
        admin_doc = await db.users.find_one({"_id": current_teacher.admin_id}, {"school_id": 1})
        if admin_doc and admin_doc.get("school_id"):
            school_scope = admin_doc["school_id"]
    if school_scope:
        query["$or"] = [
            {"school_id": school_scope},
            {"school_id": {"$exists": False}},
            {"school_id": None},
        ]

    if high_intent_only is not None:
        query["is_high_intent"] = high_intent_only
    if manual_callback_only is not None:
        query["needs_manual_callback"] = manual_callback_only

    if search:
        query["$or"] = [
            {"parent_name": {"$regex": search, "$options": "i"}},
            {"parent_phone": {"$regex": search}},
            {"student_name": {"$regex": search, "$options": "i"}}
        ]

    if appointment_status:
        query["appointment.status"] = appointment_status
    if wecom_status:
        query["wecom_status"] = wecom_status
    
    total = await db.leads.count_documents(query)
    
    skip = (page - 1) * page_size
    cursor = (
        db.leads.find(query)
        .sort([("created_at", -1)])
        .skip(skip)
        .limit(page_size)
    )
    
    raw_leads: list[dict[str, Any]] = []
    async for lead_dict in cursor:
        raw_leads.append(lead_dict)

    if _prefers_english(language):
        await asyncio.gather(*[
            _ensure_english_summary(lead_dict, db)
            for lead_dict in raw_leads
            if lead_dict.get("summary") and not lead_dict.get("en_summary")
        ])

    leads = []
    for lead_dict in raw_leads:
        lead_id = lead_dict.get("_id")
        if isinstance(lead_id, ObjectId):
            lead_id = str(lead_id)
        else:
            lead_id = str(lead_id)

        parent_name = _normalize_parent_name_candidate(lead_dict.get("parent_name")) or DEFAULT_PARENT_DISPLAY_NAME
        parent_phone = lead_dict.get("parent_phone")
        extracted_info = lead_dict.get("extracted_info") or {}
        display_name = (
            _normalize_parent_name_candidate(extracted_info.get("parent_name"))
            or _normalize_parent_name_candidate(extracted_info.get("name"))
            or parent_name
        )
        display_phone = extracted_info.get("phone") or parent_phone
        campus = _resolve_lead_campus(lead_dict)

        appointment = _serialize_appointment(lead_dict.get("appointment"), fallback_campus=campus) or {}
        appointment_name = appointment.get("parent_name") or appointment.get("guardian_name")
        appointment_phone = appointment.get("phone")
        appointment_email = appointment.get("email")
        parent_email = lead_dict.get("parent_email") or appointment_email
        chat_id_value = lead_dict.get("chat_id") or lead_dict.get("conversation_id")
        normalized_appointment_name = _normalize_parent_name_candidate(appointment_name)
        if normalized_appointment_name:
            parent_name = normalized_appointment_name
            display_name = normalized_appointment_name
        if appointment_phone:
            parent_phone = appointment_phone
            display_phone = appointment_phone

        raw_notes = lead_dict.get("notes") or []

        leads.append({
            "id": lead_id,
            "parent_name": parent_name,
            "parent_phone": parent_phone,
            "parent_email": parent_email,
            "display_name": display_name,
            "display_phone": display_phone,
            "campus": campus,
            "student_name": lead_dict.get("student_name"),
            "source": lead_dict.get("source", "unknown"),
            "is_high_intent": lead_dict.get("is_high_intent", False),
            "needs_manual_callback": lead_dict.get("needs_manual_callback", False),
            "intent_score": lead_dict.get("intent_score", 0),
            "summary": lead_dict.get("summary"),
            "en_summary": lead_dict.get("en_summary"),
            "extracted_info": extracted_info,
            "tags": lead_dict.get("tags", []),
            "notes_count": len(raw_notes),
            "next_follow_up_date": _to_shanghai_str(lead_dict.get("next_follow_up_date")),
            "created_at": _to_shanghai_str(lead_dict.get("created_at")),
            "updated_at": _to_shanghai_str(lead_dict.get("updated_at")),
            "appointment_status": appointment.get("status"),
            "appointment_timeslot": appointment.get("timeslot"),
            "appointment": appointment,
            "follow_up_owner": lead_dict.get("follow_up_owner"),
            "wecom_status": lead_dict.get("wecom_status", "not_added"),
            "wecom_contact_name": lead_dict.get("wecom_contact_name"),
            "conversation_id": chat_id_value,
            "chat_id": chat_id_value,
            "qv_chat_id": lead_dict.get("qv_chat_id"),
        })
    
    return LeadListResponse(
        total=total,
        items=leads,
        page=page,
        page_size=page_size
    )


@router.get("/export", summary="导出线索列表为 Excel")
async def export_leads(
    high_intent_only: Optional[bool] = Query(None, description="是否仅查看高意向线索"),
    manual_callback_only: Optional[bool] = Query(None, description="是否仅查看需人工回访线索"),
    search: Optional[str] = Query(None, description="搜索（姓名/手机号）"),
    appointment_status: Optional[str] = Query(None, description="预约状态筛选：pending/confirmed/rejected"),
    wecom_status: Optional[Literal["not_added", "pending", "added"]] = Query(
        None,
        description="企微添加状态筛选"
    ),
    current_teacher: UserSchema = Depends(get_current_teacher),
    db: PostgresCompatDatabase = Depends(get_database)
):
    """导出符合筛选条件的线索为 Excel."""
    query: dict[str, Any] = {}

    if high_intent_only is not None:
        query["is_high_intent"] = high_intent_only
    if manual_callback_only is not None:
        query["needs_manual_callback"] = manual_callback_only

    if search:
        query["$or"] = [
            {"parent_name": {"$regex": search, "$options": "i"}},
            {"parent_phone": {"$regex": search}},
            {"student_name": {"$regex": search, "$options": "i"}}
        ]

    if appointment_status:
        query["appointment.status"] = appointment_status
    if wecom_status:
        query["wecom_status"] = wecom_status

    cursor = (
        db.leads.find(query)
        .sort([("created_at", -1)])
    )

    items: list[dict] = []
    async for lead_dict in cursor:
        # 重用列表接口的序列化逻辑
        campus = _resolve_lead_campus(lead_dict)
        appointment = _serialize_appointment(lead_dict.get("appointment"), fallback_campus=campus) or {}
        appointment_name = appointment.get("parent_name") or appointment.get("guardian_name")
        appointment_phone = appointment.get("phone")
        appointment_email = appointment.get("email")

        parent_name = _normalize_parent_name_candidate(lead_dict.get("parent_name")) or DEFAULT_PARENT_DISPLAY_NAME
        parent_phone = lead_dict.get("parent_phone")
        extracted_info = lead_dict.get("extracted_info") or {}
        display_name = (
            _normalize_parent_name_candidate(extracted_info.get("parent_name"))
            or _normalize_parent_name_candidate(extracted_info.get("name"))
            or parent_name
        )
        display_phone = extracted_info.get("phone") or parent_phone
        campus = _resolve_lead_campus(lead_dict)

        parent_email = lead_dict.get("parent_email") or appointment_email
        normalized_appointment_name = _normalize_parent_name_candidate(appointment_name)
        if normalized_appointment_name:
            parent_name = normalized_appointment_name
            display_name = normalized_appointment_name
        if appointment_phone:
            parent_phone = appointment_phone
            display_phone = appointment_phone

        raw_notes = lead_dict.get("notes") or []

        items.append(
            {
                "parent_name": parent_name,
                "parent_phone": parent_phone,
                "parent_email": parent_email,
                "display_name": display_name,
                "display_phone": display_phone,
                "campus": campus,
                "student_name": lead_dict.get("student_name"),
                "source": lead_dict.get("source", "unknown"),
                "is_high_intent": lead_dict.get("is_high_intent", False),
                "needs_manual_callback": lead_dict.get("needs_manual_callback", False),
                "intent_score": lead_dict.get("intent_score", 0),
                "summary": lead_dict.get("summary"),
                "extracted_info": extracted_info,
                "tags": lead_dict.get("tags", []),
                "notes_count": len(raw_notes),
                "next_follow_up_date": _to_shanghai_str(lead_dict.get("next_follow_up_date")),
                "created_at": _to_shanghai_str(lead_dict.get("created_at")),
                "updated_at": _to_shanghai_str(lead_dict.get("updated_at")),
                "appointment_status": appointment.get("status"),
                "appointment_timeslot": appointment.get("timeslot"),
                "appointment": appointment,
                "follow_up_owner": lead_dict.get("follow_up_owner"),
                "wecom_status": lead_dict.get("wecom_status", "not_added"),
                "wecom_contact_name": lead_dict.get("wecom_contact_name"),
                "conversation_id": lead_dict.get("chat_id") or lead_dict.get("conversation_id"),
            }
        )

    rows = _build_export_rows(items)
    df = pd.DataFrame(rows)
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    today = datetime.now(tz=SHANGHAI_TZ).strftime("%Y%m%d")
    filename = f"leads_{today}.xlsx"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"'
    }
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.get("/my", response_model=LeadListResponse, summary="获取我的线索")
async def get_my_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_teacher: UserSchema = Depends(get_current_teacher),
):
    """当前版本已取消线索分配功能，返回空列表以保持兼容。"""
    return LeadListResponse(total=0, items=[], page=page, page_size=page_size)


@router.get("/{lead_id}", response_model=LeadDetailResponse, summary="获取线索详情")
async def get_lead_detail(
    lead_id: str,
    language: Optional[str] = Query(None, description="当前界面语言"),
    current_teacher: UserSchema = Depends(get_current_teacher),
    db: PostgresCompatDatabase = Depends(get_database)
):
    """获取线索详细信息，包括所有跟进记录"""
    query = _id_filter(lead_id)
    lead_dict = await db.leads.find_one(query)
    
    if not lead_dict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="线索不存在"
        )
    # 学校隔离校验
    school_id = None
    if current_teacher.role == "school_admin":
        school_id = current_teacher.school_id
    elif current_teacher.role == "teacher" and current_teacher.admin_id:
        admin_doc = await db.users.find_one({"_id": current_teacher.admin_id}, {"school_id": 1})
        school_id = admin_doc.get("school_id") if admin_doc else None
    if school_id and lead_dict.get("school_id") and lead_dict["school_id"] != school_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问其他学校线索")

    if _prefers_english(language) and lead_dict.get("summary") and not lead_dict.get("en_summary"):
        await _ensure_english_summary(lead_dict, db)
    
    # 格式化跟进记录
    notes = []
    raw_notes = lead_dict.get("notes") or []
    for note in raw_notes:
        if not isinstance(note, dict):
            continue
        note_id = note.get("id") or note.get("_id")
        if isinstance(note_id, ObjectId):
            note_id = str(note_id)
        elif note_id is None:
            note_id = ""
        # 获取跟进人姓名
        creator_name = None
        if note.get("created_by"):
            creator = await db.users.find_one({"_id": note["created_by"]})
            if creator:
                creator_name = creator.get("name")

        note_created_at = _to_shanghai_str(note.get("created_at"))

        notes.append({
            "id": note_id,
            "content": note.get("content", ""),
            "follow_up_method": note.get("follow_up_method") or note.get("action_type"),
            "created_by": note.get("created_by"),
            "created_by_name": creator_name,
            "created_at": note_created_at
        })

    lead_id_value = lead_dict.get("_id")
    if isinstance(lead_id_value, ObjectId):
        lead_id_str = str(lead_id_value)
    else:
        lead_id_str = str(lead_id_value)

    extracted_info = lead_dict.get("extracted_info") or {}
    campus = _resolve_lead_campus(lead_dict)
    appointment = _serialize_appointment(lead_dict.get("appointment"), fallback_campus=campus) or {}
    appointment_name = appointment.get("parent_name") or appointment.get("guardian_name")
    appointment_phone = appointment.get("phone")
    appointment_email = appointment.get("email")

    parent_name_value = _normalize_parent_name_candidate(lead_dict.get("parent_name")) or DEFAULT_PARENT_DISPLAY_NAME
    parent_phone_value = lead_dict.get("parent_phone")
    parent_email_value = lead_dict.get("parent_email")

    normalized_appointment_name = _normalize_parent_name_candidate(appointment_name)
    if normalized_appointment_name:
        parent_name_value = normalized_appointment_name
    if appointment_phone:
        parent_phone_value = appointment_phone
    if appointment_email and not parent_email_value:
        parent_email_value = appointment_email

    display_name = (
        normalized_appointment_name
        or _normalize_parent_name_candidate(extracted_info.get("parent_name"))
        or _normalize_parent_name_candidate(extracted_info.get("name"))
        or parent_name_value
    )
    display_phone = appointment_phone or extracted_info.get("phone") or parent_phone_value
    parent_id = lead_dict.get("parent_id")
    if isinstance(parent_id, ObjectId):
        parent_id = str(parent_id)
    else:
        parent_id = str(parent_id)

    conversation_history: List[dict] = []
    chat_id = lead_dict.get("chat_id") or lead_dict.get("conversation_id")
    if chat_id:
        candidates: List[Any] = [chat_id]
        if ObjectId.is_valid(chat_id):
            candidates.append(ObjectId(chat_id))
        conv_lookup = {"conversation_id": {"$in": candidates}}
        cursor = db.messages.find(conv_lookup).sort("_id", 1)
        async for msg in cursor:
            if _should_hide_lead_conversation_message(msg):
                continue
            created = _to_shanghai_str(msg.get("created_at"))
            sender_type = msg.get("sender_type")
            content = msg.get("content", "")
            sender_name = "招生助手"
            if sender_type == "parent":
                sender_name = display_name or parent_name_value
            elif sender_type == "teacher":
                sender_name = "招生老师"

            conversation_history.append({
                "id": str(msg.get("_id")),
                "sender_type": sender_type,
                "sender_name": sender_name,
                "content": content,
                "created_at": created,
            })

    stored_first_message_at = _to_shanghai_str(lead_dict.get("first_message_at"))

    wecom_chat_history = _serialize_wecom_messages(lead_dict.get("wecom_chat_history"))

    return LeadDetailResponse(
        id=lead_id_str,
        parent_id=parent_id,
        parent_name=parent_name_value or "",
        parent_phone=parent_phone_value,
        parent_email=parent_email_value,
        display_name=display_name,
        display_phone=display_phone,
        campus=campus,
        extracted_info=extracted_info,
        student_name=lead_dict.get("student_name"),
        student_age=lead_dict.get("student_age"),
        student_grade=lead_dict.get("student_grade"),
        is_high_intent=lead_dict.get("is_high_intent", False),
        needs_manual_callback=lead_dict.get("needs_manual_callback", False),
        source=lead_dict.get("source", "unknown"),
        intent_score=lead_dict.get("intent_score", 0),
        summary=lead_dict.get("summary"),
        en_summary=lead_dict.get("en_summary"),
        conversation_id=chat_id,
        chat_id=chat_id,
        qv_chat_id=lead_dict.get("qv_chat_id"),
        first_message_at=stored_first_message_at,
        tags=lead_dict.get("tags", []),
        notes=notes,
        next_follow_up_date=_to_shanghai_str(lead_dict.get("next_follow_up_date")),
        created_at=_to_shanghai_str(lead_dict.get("created_at")),
        updated_at=_to_shanghai_str(lead_dict.get("updated_at")),
        appointment=appointment,
        conversation_history=conversation_history,
        follow_up_owner=lead_dict.get("follow_up_owner"),
        wecom_status=lead_dict.get("wecom_status", "not_added"),
        wecom_chat_history=wecom_chat_history,
        wecom_contact_name=lead_dict.get("wecom_contact_name"),
        wecom_contact_id=lead_dict.get("wecom_contact_id"),
    )



@router.post("", summary="创建线索")
async def create_lead(
            request: CreateLeadRequest,
            current_teacher: UserSchema = Depends(get_current_teacher),
            db: PostgresCompatDatabase = Depends(get_database)):
    """
    手动创建线索（教师）
    """
    # 查找家长用户（如果不存在则创建）
    parent = await db.users.find_one({"phone": request.parent_phone})
    
    if not parent:
        # 创建新家长用户
        from app.models.user import UserSchema as User
        new_parent = User(
            phone=request.parent_phone,
            name=request.parent_name,
            role="parent",
            email=request.parent_email
        )
        parent_dict = new_parent.model_dump()
        await db.users.insert_one(parent_dict)
        parent_id = new_parent.id
    else:
        parent_id = parent["_id"]
    
    # 创建线索
    lead = LeadSchema(
        parent_id=parent_id,
        parent_name=request.parent_name,
        parent_phone=request.parent_phone,
        parent_email=request.parent_email,
        student_name=request.student_name,
        student_age=request.student_age,
        student_grade=request.student_grade,
        source=request.source,
        is_high_intent=request.is_high_intent,
        needs_manual_callback=request.needs_manual_callback,
        tags=request.tags or [],
        follow_up_owner=request.follow_up_owner.model_dump() if request.follow_up_owner else None,
        wecom_contact_name=request.wecom_contact_name,
    )
    
    lead_dict = lead.model_dump(by_alias=True, exclude_none=True)
    await db.leads.insert_one(lead_dict)
    
    logger.info(f"教师 {current_teacher.phone} 创建线索: {lead.id}")
    
    return {
        "message": "线索创建成功",
        "lead_id": lead.id
    }


@router.put("/{lead_id}", summary="更新线索")
async def update_lead(
    lead_id: str,
    request: UpdateLeadRequest,
    current_teacher: UserSchema = Depends(get_current_teacher),
    db: PostgresCompatDatabase = Depends(get_database)
):
    """
    更新线索信息（教师）
    """
    # 检查线索是否存在
    lead_dict = await db.leads.find_one(_id_filter(lead_id))
    if not lead_dict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="线索不存在"
        )
    
    # 构建更新数据
    update_data = {"updated_at": datetime.utcnow()}
    
    if request.is_high_intent is not None:
        update_data["is_high_intent"] = request.is_high_intent

    if request.needs_manual_callback is not None:
        update_data["needs_manual_callback"] = request.needs_manual_callback
    
    if request.student_name is not None:
        update_data["student_name"] = request.student_name
    
    if request.student_age is not None:
        update_data["student_age"] = request.student_age
    
    if request.student_grade is not None:
        update_data["student_grade"] = request.student_grade
    
    if request.parent_email is not None:
        update_data["parent_email"] = request.parent_email
    
    if request.tags is not None:
        update_data["tags"] = request.tags
    
    if request.next_follow_up_date is not None:
        update_data["next_follow_up_date"] = request.next_follow_up_date

    if request.wecom_status is not None:
        update_data["wecom_status"] = request.wecom_status

    if request.follow_up_owner is not None:
        update_data["follow_up_owner"] = request.follow_up_owner.model_dump()
    if request.wecom_contact_name is not None:
        update_data["wecom_contact_name"] = request.wecom_contact_name
    
    # 更新到数据库
    await db.leads.update_one(
        _id_filter(lead_id),
        {"$set": update_data}
    )
    
    logger.info(f"教师 {current_teacher.phone} 更新线索 {lead_id}")
    
    return {"message": "线索更新成功"}


@router.post("/{lead_id}/notes", summary="添加跟进记录")
async def add_follow_up_note(
    lead_id: str,
    request: AddNoteRequest,
    current_teacher: UserSchema = Depends(get_current_teacher),
    db: PostgresCompatDatabase = Depends(get_database)
):
    """
    添加跟进记录
    """
    # 检查线索是否存在
    lead_dict = await db.leads.find_one(_id_filter(lead_id))
    if not lead_dict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="线索不存在"
        )
    
    # 验证跟进方式
    valid_methods = ["phone", "wechat", "email", "visit", "other"]
    if request.follow_up_method not in valid_methods:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的跟进方式，有效值: {', '.join(valid_methods)}"
        )
    
    # 创建跟进记录
    note = FollowUpNote(
        content=request.content,
        follow_up_method=request.follow_up_method,
        created_by=current_teacher.id,
        created_by_name=current_teacher.name,
    )
    
    # 添加到线索
    await db.leads.update_one(
        _id_filter(lead_id),
        {
            "$push": {"notes": note.model_dump()},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    
    logger.info(f"教师 {current_teacher.phone} 在线索 {lead_id} 添加跟进记录")
    
    return {
        "message": "跟进记录添加成功",
        "note_id": note.id
    }


@router.put("/{lead_id}/notes/{note_id}", summary="更新跟进记录")
async def update_follow_up_note(
    lead_id: str,
    note_id: str,
    request: UpdateNoteRequest,
    current_teacher: UserSchema = Depends(get_current_teacher),
    db: PostgresCompatDatabase = Depends(get_database),
):
    """更新指定跟进记录"""
    lead_dict = await db.leads.find_one(_id_filter(lead_id))
    if not lead_dict:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="线索不存在")

    # 验证跟进方式
    valid_methods = ["phone", "wechat", "email", "visit", "other", None]
    if request.follow_up_method not in valid_methods:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的跟进方式，有效值: phone/wechat/email/visit/other"
        )

    raw_notes = lead_dict.get("notes") or []
    updated_notes = []
    updated = False
    now = datetime.utcnow()

    for note in raw_notes:
        if not isinstance(note, dict):
            updated_notes.append(note)
            continue
        current_note_id = note.get("id") or note.get("_id")
        if isinstance(current_note_id, ObjectId):
            current_note_id = str(current_note_id)
        elif current_note_id is not None:
            current_note_id = str(current_note_id)

        if current_note_id == note_id:
            next_note = dict(note)
            next_note["id"] = current_note_id or note_id
            next_note["content"] = request.content
            next_note["follow_up_method"] = request.follow_up_method or "other"
            next_note["updated_at"] = now
            updated_notes.append(next_note)
            updated = True
            continue

        updated_notes.append(note)

    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="跟进记录不存在")

    await db.leads.update_one(
        _id_filter(lead_id),
        {
            "$set": {
                "notes": updated_notes,
                "updated_at": now,
            }
        },
    )
    return {"message": "跟进记录已更新"}


@router.delete("/{lead_id}/notes/{note_id}", summary="删除跟进记录")
async def delete_follow_up_note(
    lead_id: str,
    note_id: str,
    current_teacher: UserSchema = Depends(get_current_teacher),
    db: PostgresCompatDatabase = Depends(get_database),
):
    """删除指定跟进记录"""
    lead_dict = await db.leads.find_one(_id_filter(lead_id))
    if not lead_dict:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="线索不存在")

    raw_notes = lead_dict.get("notes") or []
    remaining_notes = []
    removed = False

    for note in raw_notes:
        if not isinstance(note, dict):
            remaining_notes.append(note)
            continue
        current_note_id = note.get("id") or note.get("_id")
        if isinstance(current_note_id, ObjectId):
            current_note_id = str(current_note_id)
        elif current_note_id is not None:
            current_note_id = str(current_note_id)

        if current_note_id == note_id:
            removed = True
            continue

        remaining_notes.append(note)

    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="跟进记录不存在")

    await db.leads.update_one(
        _id_filter(lead_id),
        {
            "$set": {
                "notes": remaining_notes,
                "updated_at": datetime.utcnow(),
            }
        },
    )
    return {"message": "跟进记录已删除"}


@router.get("/{lead_id}/notes", summary="获取跟进记录")
async def get_follow_up_notes(
    lead_id: str,
    current_teacher: UserSchema = Depends(get_current_teacher),
    db: PostgresCompatDatabase = Depends(get_database)
):
    """
    获取线索的所有跟进记录
    """
    lead_dict = await db.leads.find_one(_id_filter(lead_id))
    
    if not lead_dict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="线索不存在"
        )
    
    # 格式化跟进记录
    notes = []
    for note in lead_dict.get("notes", []):
        # 获取跟进人姓名
        creator_name = None
        if note.get("created_by"):
            creator = await db.users.find_one({"_id": note["created_by"]})
            if creator:
                creator_name = creator.get("name")
        
        note_created_at = note.get("created_at")
        if isinstance(note_created_at, datetime):
            note_created_at = note_created_at.isoformat()

        notes.append({
            "id": note["id"],
            "content": note["content"],
            "follow_up_method": note["follow_up_method"],
            "created_by": note.get("created_by"),
            "created_by_name": creator_name,
            "created_at": note_created_at
        })
    
    return {
        "total": len(notes),
        "items": notes
    }


@router.delete("/{lead_id}", summary="删除线索")
async def delete_lead(
    lead_id: str,
    current_teacher: UserSchema = Depends(get_current_teacher),
    db: PostgresCompatDatabase = Depends(get_database)
):
    """
    删除线索（从数据库中删除记录）
    """
    result = await db.leads.delete_one(_id_filter(lead_id))
    
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="线索不存在"
        )
    
    logger.info(f"教师 {current_teacher.phone} 删除线索 {lead_id}")
    
    return {"message": "线索已删除"}
class FollowUpOwnerPayload(BaseModel):
    """跟进老师信息"""
    name: str = Field(..., description="老师姓名", min_length=1)
    campus: Optional[str] = Field(default=None, description="负责校区")
    wechat_id: Optional[str] = Field(default=None, description="企业微信 ID")
    qr_code_url: Optional[str] = Field(default=None, description="二维码链接")
    contact_phone: Optional[str] = Field(default=None, description="联系方式")
