"""
线索模型 - 管理招生线索（由高意向会话自动创建）
"""
from pydantic import BaseModel, Field, AliasChoices
from typing import Optional, Literal
from datetime import datetime
from bson import ObjectId

from .conversation import AppointmentInfo


class LeadSchema(BaseModel):
    """线索数据模型"""
    id: Optional[str] = Field(default=None, alias="_id")
    
    # 关联信息
    parent_id: str = Field(..., description="家长用户ID")
    conversation_id: str = Field(
        ...,
        serialization_alias="chat_id",
        validation_alias=AliasChoices("chat_id", "conversation_id"),
        description="来源会话ID（星途 chatId）"
    )
    qv_chat_id: Optional[str] = Field(
        default=None,
        description="企业微信聊天唯一标识 qvChatId"
    )
    
    # 线索状态
    is_high_intent: bool = Field(default=False, description="是否高意向线索")
    needs_manual_callback: bool = Field(default=False, description="是否需要人工电话回访")
    source: Optional[str] = Field(default=None, description="线索来源渠道")
    
    # 家长信息（冗余存储，方便查询）
    parent_phone: Optional[str] = Field(default=None, description="家长手机号")
    parent_name: Optional[str] = Field(default=None, description="家长姓名")
    parent_email: Optional[str] = Field(default=None, description="家长邮箱")
    campus: Optional[str] = Field(default=None, description="意向校区")
    intended_product: Optional[str] = Field(default=None, description="意向产品")
    interest_level: Optional[str] = Field(default=None, description="意向度")
    school_id: Optional[str] = Field(default=None, description="所属学校")
    has_foreign_passport: bool = Field(default=False, description="家里是否有人是外籍")
    has_appointment: bool = Field(default=False, description="是否已预约")
    follow_up_owner: Optional[dict] = Field(default=None, description="跟进老师信息")
    wecom_status: Literal["not_added", "pending", "added"] = Field(
        default="not_added",
        description="企业微信添加状态"
    )
    wecom_contact_id: Optional[str] = Field(default=None, description="企业微信外部联系人ID")
    wecom_contact_name: Optional[str] = Field(default=None, description="企业微信昵称")
    wecom_chat_history: list[dict] = Field(default_factory=list, description="企业微信聊天记录")
    
    # 学生信息
    student_name: Optional[str] = Field(default=None, description="学生姓名")
    student_age: Optional[int] = Field(default=None, description="学生年龄")
    grade_applying: Optional[str] = Field(default=None, description="申请年级")

    # AI分析结果
    intent_score: int = Field(default=0, ge=0, le=100, description="意向评分(0-100)")
    summary: Optional[str] = Field(default=None, description="会话摘要")
    en_summary: Optional[str] = Field(default=None, description="英文会话摘要")

    # 提取的结构化信息
    extracted_info: Optional[dict] = Field(default=None, description="提取的详细信息")

    # 跟进信息
    follow_up_notes: list['FollowUpNote'] = Field(default_factory=list, description="跟进记录（历史兼容字段，推荐使用 notes 集合字段）")
    next_follow_up_date: Optional[datetime] = Field(default=None, description="下次跟进日期")
    first_message_at: Optional[datetime] = Field(default=None, description="首次消息时间（用于咨询时间展示）")

    # 标签
    tags: list[str] = Field(default_factory=list, description="标签")
    appointment: Optional[AppointmentInfo] = Field(default=None, description="预约信息")
    
    # 时间戳
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }
        json_schema_extra = {
            "example": {
                "parent_id": "507f1f77bcf86cd799439011",
                "chat_id": "507f1f77bcf86cd799439012",
                "is_high_intent": True,
                "needs_manual_callback": True,
                "parent_phone": "13800138000",
                "parent_name": "张三",
                "student_name": "张小明",
                "student_age": 10,
                "grade_applying": "G6",
                "intent_score": 85,
                "summary": "家长对数学课程很感兴趣，孩子数学成绩优异"
            }
        }
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return self.model_dump(by_alias=True, exclude_none=True)


class FollowUpNote(BaseModel):
    """跟进记录"""
    id: str = Field(default_factory=lambda: str(ObjectId()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    created_by: str = Field(..., description="创建人ID")
    created_by_name: Optional[str] = Field(default=None, description="创建人姓名")
    content: str = Field(..., description="跟进内容")
    action_type: Optional[Literal["call", "wechat", "email", "visit", "other"]] = Field(
        default=None, 
        description="跟进方式"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "created_by_name": "李老师",
                "content": "已通过电话联系家长，家长表示下周可以来访校",
                "action_type": "call"
            }
        }


class LeadCreateRequest(BaseModel):
    """创建线索请求（通常由系统自动创建）"""
    parent_id: str
    conversation_id: str
    intent_score: int = Field(..., ge=0, le=100)
    summary: Optional[str] = None
    is_high_intent: bool = False


class LeadUpdateRequest(BaseModel):
    """更新线索请求"""
    is_high_intent: Optional[bool] = None
    next_follow_up_date: Optional[datetime] = None
    tags: Optional[list[str]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "is_high_intent": True,
                "next_follow_up_date": "2025-10-15T10:00:00"
            }
        }


class LeadAddNoteRequest(BaseModel):
    """添加跟进记录请求"""
    content: str = Field(..., min_length=1)
    action_type: Optional[Literal["call", "wechat", "email", "visit", "other"]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "content": "已通过电话联系家长，家长表示下周可以来访校",
                "action_type": "call"
            }
        }


class LeadResponse(BaseModel):
    """线索响应"""
    id: str = Field(..., alias="_id")
    parent_id: str
    conversation_id: Optional[str] = None
    chat_id: Optional[str] = Field(
        default=None,
        description="星途 chatId，等同 conversation_id"
    )
    qv_chat_id: Optional[str] = Field(
        default=None,
        description="企业微信 qvChatId"
    )
    is_high_intent: bool
    needs_manual_callback: bool
    parent_phone: Optional[str] = None
    parent_name: Optional[str] = None
    intended_product: Optional[str] = None
    interest_level: Optional[str] = None
    student_name: Optional[str] = None
    student_age: Optional[int] = None
    grade_applying: Optional[str] = None
    intent_score: int
    summary: Optional[str] = None
    en_summary: Optional[str] = None
    follow_up_notes: list[FollowUpNote] = []
    next_follow_up_date: Optional[datetime] = None
    tags: list[str] = []
    appointment: Optional[AppointmentInfo] = None
    follow_up_owner: Optional[dict] = None
    wecom_status: Literal["not_added", "pending", "added"] = "not_added"
    wecom_contact_name: Optional[str] = None
    wecom_chat_history: list[dict] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class LeadListItem(BaseModel):
    """线索列表项（简化版）"""
    id: str = Field(..., alias="_id")
    is_high_intent: bool
    needs_manual_callback: bool
    conversation_id: Optional[str] = None
    chat_id: Optional[str] = None
    qv_chat_id: Optional[str] = None
    parent_phone: str
    parent_name: Optional[str] = None
    intended_product: Optional[str] = None
    interest_level: Optional[str] = None
    student_name: Optional[str] = None
    grade_applying: Optional[str] = None
    intent_score: int
    next_follow_up_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    wecom_status: Literal["not_added", "pending", "added"] = "not_added"
    follow_up_owner: Optional[dict] = None
    wecom_contact_name: Optional[str] = None
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class LeadStatistics(BaseModel):
    """线索统计数据"""
    total: int = 0
    high_intent: int = 0
    today_new: int = 0
    week_new: int = 0
