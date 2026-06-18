"""
会话模型 - 管理家长与AI的对话会话
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from bson import ObjectId


class AppointmentInfo(BaseModel):
    """预约信息"""
    campus: Optional[str] = Field(default=None, description="预约校区")
    timeslot: str = Field(..., description="预约时间段")
    status: Literal["pending", "confirmed", "rejected"] = Field(
        default="pending", description="预约状态"
    )
    parent_name: Optional[str] = Field(default=None, description="家长姓名")
    phone: Optional[str] = Field(default=None, description="联系电话")
    email: Optional[str] = Field(default=None, description="邮箱")
    note: Optional[str] = Field(default=None, description="备注")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = Field(default=None, description="创建人 ID")
    confirmed_by: Optional[str] = Field(default=None, description="确认老师 ID")


class ConversationSchema(BaseModel):
    """会话数据模型"""
    id: Optional[str] = Field(default=None, alias="_id")
    
    parent_id: str = Field(..., description="家长用户ID")
    school_id: Optional[str] = Field(default=None, description="所属学校")
    assistant_id: Optional[str] = Field(default=None, description="所属助手")
    appointment: Optional[AppointmentInfo] = Field(default=None, description="预约信息")
    source_channel: Optional[str] = Field(default=None, description="渠道来源缩写")
    channel_appointment_logged: bool = Field(default=False, description="是否已记录渠道预约")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = Field(default=None, description="关闭时间")
    last_message_at: Optional[datetime] = Field(default=None, description="最近一条消息时间")
    
    # 统计字段
    message_count: int = Field(default=0, description="消息数量")
    
    class Config:
        populate_by_name = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }
        json_schema_extra = {
            "example": {
                "parent_id": "507f1f77bcf86cd799439011",
                "message_count": 5,
                "last_message_at": "2025-10-01T09:30:00Z"
            }
        }
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return self.model_dump(by_alias=True, exclude_none=True)


class ConversationCreateRequest(BaseModel):
    """创建会话请求（通常自动创建，无需额外参数）"""
    language: str = Field(default="zh-CN", description="欢迎语语言代码")
    source: Optional[str] = Field(default=None, description="渠道来源缩写（xhs/dy等）")
    school_id: Optional[str] = Field(default=None, description="所属学校")
    assistant_id: Optional[str] = Field(default=None, description="所属助手")


class ConversationUpdateRequest(BaseModel):
    """更新会话请求"""
    appointment: Optional[AppointmentInfo] = None
    message_count: Optional[int] = None
    closed_at: Optional[datetime] = None


class ConversationResponse(BaseModel):
    """会话响应"""
    id: str = Field(..., alias="_id")
    parent_id: str
    school_id: Optional[str] = None
    assistant_id: Optional[str] = None
    message_count: int = 0
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
    appointment: Optional[AppointmentInfo] = None
    last_message_at: Optional[datetime] = None
    source_channel: Optional[str] = None
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ConversationListItem(BaseModel):
    """会话列表项（简化版）"""
    id: str = Field(..., alias="_id")
    message_count: int = 0
    created_at: datetime
    updated_at: datetime
    last_message_at: Optional[datetime] = None
    
    # 最后一条消息预览
    last_message_preview: Optional[str] = None
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
