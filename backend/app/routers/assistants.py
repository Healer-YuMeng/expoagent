from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.dependencies import get_current_admin
from app.db import PostgresCompatDatabase, get_database
from app.models.user import UserSchema
from app.services.assistant_service import AssistantService


router = APIRouter(prefix="/api/v1/assistants", tags=["助手配置"])


class AssistantCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, description="助手名称")
    school_id: Optional[str] = Field(default=None, description="学校 ID，仅 super admin 可指定")


class AssistantUpdateRequest(BaseModel):
    name: Optional[str] = None
    knowledge_base_id: Optional[str] = None
    is_active: Optional[bool] = None


def _resolve_school_scope(current_user: UserSchema, requested_school_id: Optional[str]) -> str:
    if current_user.role == "school_admin":
        if not current_user.school_id:
            raise HTTPException(status_code=400, detail="管理员未绑定学校")
        return current_user.school_id
    school_id = (requested_school_id or "").strip()
    if not school_id:
        raise HTTPException(status_code=400, detail="school_id 不能为空")
    return school_id


@router.get("", summary="助手列表")
async def list_assistants(
    school_id: Optional[str] = Query(default=None),
    db: PostgresCompatDatabase = Depends(get_database),
    current_user: UserSchema = Depends(get_current_admin),
):
    scope_school = _resolve_school_scope(current_user, school_id)
    service = AssistantService(db)
    return {"items": await service.list_assistants(school_id=scope_school)}


@router.post("", summary="新建助手")
async def create_assistant(
    payload: AssistantCreateRequest,
    db: PostgresCompatDatabase = Depends(get_database),
    current_user: UserSchema = Depends(get_current_admin),
):
    scope_school = _resolve_school_scope(current_user, payload.school_id)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="name 不能为空")
    service = AssistantService(db)
    existing = await service.get_assistant_by_name(school_id=scope_school, name=name)
    if existing:
        raise HTTPException(status_code=409, detail="助手名称已存在")
    assistant = await service.create_assistant(
        name=name,
        school_id=scope_school,
        admin_id=current_user.id,
    )
    return assistant


@router.patch("/{assistant_id}", summary="更新助手")
async def update_assistant(
    assistant_id: str,
    payload: AssistantUpdateRequest,
    db: PostgresCompatDatabase = Depends(get_database),
    current_user: UserSchema = Depends(get_current_admin),
):
    service = AssistantService(db)
    assistant = await service.get_assistant(assistant_id)
    if not assistant:
        raise HTTPException(status_code=404, detail="助手不存在")
    if current_user.role == "school_admin" and assistant.get("school_id") != current_user.school_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权操作其他学校助手")

    knowledge_base_id = payload.knowledge_base_id
    if knowledge_base_id:
        kb = await db["rag_knowledge_bases"].find_one({"_id": knowledge_base_id})
        if not kb:
            raise HTTPException(status_code=404, detail="知识库不存在")
        if str(kb.get("school_id") or "") != str(assistant.get("school_id") or ""):
            raise HTTPException(status_code=400, detail="知识库不属于当前助手所在学校")

    updated = await service.update_assistant(
        assistant_id,
        name=payload.name.strip() if isinstance(payload.name, str) and payload.name.strip() else None,
        knowledge_base_id=knowledge_base_id,
        is_active=payload.is_active,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="助手不存在")
    return updated
