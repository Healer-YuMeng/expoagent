import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.dependencies import get_current_super_admin, get_current_admin
from app.db import PostgresCompatDatabase, get_database
from app.models.user import UserSchema
from app.services.assistant_service import AssistantService
from app.services.prompt_service import get_prompt_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/prompts", tags=["系统提示词"])


class PromptResponse(BaseModel):
    key: str
    content: str
    locale: Optional[str] = None
    school_id: Optional[str] = None
    assistant_id: Optional[str] = None
    version: Optional[int] = None
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None
    is_default: bool = False
    default_content: Optional[str] = None


class PromptUpdateRequest(BaseModel):
    content: str = Field(..., description="提示词内容")
    locale: Optional[str] = Field(default=None, description="语言代码，可选")
    school_id: Optional[str] = Field(default=None, description="学校ID，可选（super admin 指定）")
    assistant_id: Optional[str] = Field(default=None, description="助手ID")


@router.get("/{key}", response_model=PromptResponse, summary="获取提示词（含默认兜底）")
async def get_prompt(
    key: str,
    locale: Optional[str] = Query(default=None, description="可选语言代码"),
    school_id: Optional[str] = Query(default=None, description="学校ID，普通管理员自动限定为自身学校"),
    assistant_id: Optional[str] = Query(default=None, description="助手ID"),
    current_user: UserSchema = Depends(get_current_admin),
    db: PostgresCompatDatabase = Depends(get_database),
):
    prompt_service = get_prompt_service()
    scope_school = school_id
    if current_user.role == "admin":
        scope_school = current_user.school_id
    scope_assistant = assistant_id
    if assistant_id:
        assistant = await AssistantService(db).get_assistant(assistant_id)
        if not assistant:
            raise HTTPException(status_code=404, detail="助手不存在")
        if current_user.role == "admin" and assistant.get("school_id") != current_user.school_id:
            raise HTTPException(status_code=403, detail="无权访问其他学校助手")
        scope_school = assistant.get("school_id") or scope_school
    result = await prompt_service.get_prompt_with_meta(
        key,
        locale=locale,
        school_id=scope_school,
        assistant_id=scope_assistant,
    )
    meta = result.get("meta") or {}
    return PromptResponse(
        key=key,
        content=result.get("content", ""),
        locale=meta.get("locale") if meta else locale,
        school_id=meta.get("school_id") if meta else scope_school,
        assistant_id=meta.get("assistant_id") if meta else scope_assistant,
        version=meta.get("version") if meta else None,
        updated_at=meta.get("updated_at") if meta else None,
        updated_by=meta.get("updated_by") if meta else None,
        is_default=result.get("is_default", False),
        default_content=result.get("default_content"),
    )


@router.put("/{key}", response_model=PromptResponse, summary="更新并激活提示词")
async def update_prompt(
    key: str,
    payload: PromptUpdateRequest,
    current_user: UserSchema = Depends(get_current_admin),
    db: PostgresCompatDatabase = Depends(get_database),
):
    if not payload.content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="content 不能为空",
        )
    if current_user.role == "admin":
        scope_school = current_user.school_id
    else:
        scope_school = payload.school_id
    scope_assistant = payload.assistant_id
    if scope_assistant:
        assistant = await AssistantService(db).get_assistant(scope_assistant)
        if not assistant:
            raise HTTPException(status_code=404, detail="助手不存在")
        if current_user.role == "admin" and assistant.get("school_id") != current_user.school_id:
            raise HTTPException(status_code=403, detail="无权操作其他学校助手")
        scope_school = assistant.get("school_id") or scope_school
    prompt_service = get_prompt_service()
    doc = await prompt_service.set_prompt(
        key=key,
        content=payload.content,
        locale=payload.locale,
        school_id=scope_school,
        assistant_id=scope_assistant,
        updated_by=current_user.phone or current_user.name,
    )
    return PromptResponse(
        key=doc.get("key", key),
        content=doc.get("content", ""),
        locale=doc.get("locale"),
        school_id=doc.get("school_id"),
        assistant_id=doc.get("assistant_id"),
        version=doc.get("version"),
        updated_at=doc.get("updated_at"),
        updated_by=doc.get("updated_by"),
        is_default=False,
        default_content=None,
    )
