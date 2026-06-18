from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field


class DocRecord(BaseModel):
    id: str = Field(..., description="文档 ID")
    name: str
    object_name: str
    size: int
    knowledge_base_id: str | None = None
    school_id: str | None = None
    admin_id: str | None = None
    status: str = "pending"
    chunk_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ChunkRecord(BaseModel):
    id: str
    doc_id: str
    knowledge_base_id: str | None = None
    school_id: str | None = None
    admin_id: str | None = None
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class KnowledgeBaseRecord(BaseModel):
    id: str = Field(..., description="知识库 ID")
    name: str
    school_id: str
    admin_id: str | None = None
    description: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
