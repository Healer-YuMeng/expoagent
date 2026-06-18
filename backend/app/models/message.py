"""
消息模型 - 管理会话中的具体消息
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from bson import ObjectId


class MessageSchema(BaseModel):
    """消息数据模型"""
    id: Optional[str] = Field(default=None, alias="_id")
    
    conversation_id: str = Field(..., description="所属会话ID")
    sender_id: Optional[str] = Field(default=None, description="发送者ID（家长ID或系统ID，bot消息可为空）")
    sender_type: Literal["parent", "bot", "teacher"] = Field(
        ..., 
        description="发送者类型: parent-家长, bot-AI助理, teacher-老师"
    )
    sender_name: Optional[str] = Field(default=None, description="发送者姓名")
    
    content: str = Field(..., min_length=1, description="消息内容")
    # 消息元数据
    metadata: Optional[dict] = Field(default=None, description="消息元数据")
    attachments: list[str] = Field(default_factory=list, description="附件URL列表")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_read: bool = Field(default=False, description="是否已读（管理员端）")
    
    class Config:
        populate_by_name = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }
        json_schema_extra = {
            "example": {
                "conversation_id": "507f1f77bcf86cd799439011",
                "sender_id": "507f1f77bcf86cd799439012",
                "sender_type": "parent",
                "content": "我想了解一下你们学校的课程设置"
            }
        }
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return self.model_dump(by_alias=True, exclude_none=True)


class MessageCreateRequest(BaseModel):
    """创建消息请求（家长端发送消息）"""
    content: str = Field(..., min_length=1, max_length=5000)
    
    class Config:
        json_schema_extra = {
            "example": {
                "content": "我想了解一下你们学校的课程设置"
            }
        }


class MessageResponse(BaseModel):
    """消息响应"""
    id: str = Field(..., alias="_id")
    conversation_id: str
    sender_id: Optional[str] = None
    sender_type: str
    content: str
    created_at: datetime
    is_read: bool = False
    metadata: Optional[dict] = None
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class MessageWithSenderInfo(BaseModel):
    """消息响应（包含发送者信息）"""
    id: str = Field(..., alias="_id")
    conversation_id: str
    sender_id: Optional[str] = None
    sender_type: str
    content: str
    created_at: datetime
    is_read: bool = False
    
    # 发送者信息
    sender_name: Optional[str] = None
    sender_phone: Optional[str] = None
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
