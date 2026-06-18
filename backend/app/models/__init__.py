"""
数据模型包 - 导出所有数据模型
"""
from .user import (
    UserSchema,
    UserCreateRequest,
    UserLoginRequest,
    UserResponse,
    TokenResponse
)

from .conversation import (
    ConversationSchema,
    ConversationCreateRequest,
    ConversationUpdateRequest,
    ConversationResponse,
    ConversationListItem
)

from .message import (
    MessageSchema,
    MessageCreateRequest,
    MessageResponse,
    MessageWithSenderInfo
)

from .lead import (
    LeadSchema,
    FollowUpNote,
    LeadCreateRequest,
    LeadUpdateRequest,
    LeadAddNoteRequest,
    LeadResponse,
    LeadListItem,
    LeadStatistics
)

__all__ = [
    # User models
    "UserSchema",
    "UserCreateRequest",
    "UserLoginRequest",
    "UserResponse",
    "TokenResponse",
    
    # Conversation models
    "ConversationSchema",
    "ConversationCreateRequest",
    "ConversationUpdateRequest",
    "ConversationResponse",
    "ConversationListItem",
    
    # Message models
    "MessageSchema",
    "MessageCreateRequest",
    "MessageResponse",
    "MessageWithSenderInfo",
    
    # Lead models
    "LeadSchema",
    "FollowUpNote",
    "LeadCreateRequest",
    "LeadUpdateRequest",
    "LeadAddNoteRequest",
    "LeadResponse",
    "LeadListItem",
    "LeadStatistics",
]
