from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AssistantSchema(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    name: str
    school_id: str
    admin_id: Optional[str] = None
    knowledge_base_id: Optional[str] = None
    knowledge_base_ids: list[str] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
