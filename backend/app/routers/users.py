import logging
from datetime import datetime
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.dependencies import get_current_admin, get_current_super_admin
from app.db import PostgresCompatDatabase, get_database
from app.models.user import UserSchema

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/users", tags=["账号管理"])


class UserCreatePayload(BaseModel):
    phone: str
    password: str = Field(..., min_length=3)
    role: Literal["teacher", "school_admin"]
    name: Optional[str] = None
    email: Optional[str] = None
    school_id: Optional[str] = None
    school_name: Optional[str] = None
    admin_id: Optional[str] = None


class UserUpdatePayload(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = Field(default=None, min_length=3)
    is_active: Optional[bool] = None
    school_id: Optional[str] = None
    school_name: Optional[str] = None


def _serialize_user(doc: dict) -> dict:
    doc = dict(doc)
    doc["id"] = str(doc.get("_id") or doc.get("id"))
    doc.pop("_id", None)
    doc.pop("password_hash", None)
    return doc


@router.post("", summary="创建用户（管理员）")
async def create_user(
    payload: UserCreatePayload,
    current_user: UserSchema = Depends(get_current_admin),
    db: PostgresCompatDatabase = Depends(get_database),
):
    """school_admin 仅能创建教师；super_admin 仅能创建学校管理员"""
    if current_user.role == "school_admin":
        if payload.role != "teacher":
            raise HTTPException(status_code=403, detail="学校管理员只能创建教师账号")
        school_id = current_user.school_id
        school_name = current_user.school_name
        admin_id = current_user.id
    else:  # super_admin
        if payload.role != "school_admin":
            raise HTTPException(status_code=403, detail="超级管理员仅能创建学校管理员账号")
        if not payload.school_id:
            raise HTTPException(status_code=400, detail="创建学校管理员必须指定 school_id")
        school_id = payload.school_id
        school_name = payload.school_name
        admin_id = None

    # 唯一性检查
    exists = await db.users.find_one({"phone": payload.phone})
    if exists:
        raise HTTPException(status_code=400, detail="账号已存在")

    user = UserSchema(
        phone=payload.phone,
        password_hash=UserSchema.hash_password(payload.password),
        role=payload.role,  # type: ignore[arg-type]
        name=payload.name,
        email=payload.email,
        school_id=school_id,
        school_name=school_name,
        admin_id=admin_id,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    doc = user.model_dump(by_alias=True, exclude=["id"])
    doc.pop("_id", None)
    await db.users.insert_one(doc)
    return _serialize_user(doc)


@router.get("", summary="列表查询用户（管理员）")
async def list_users(
    role: Optional[str] = Query(default=None, description="teacher 或 school_admin"),
    db: PostgresCompatDatabase = Depends(get_database),
    current_user: UserSchema = Depends(get_current_admin),
):
    items = []
    if current_user.role == "school_admin":
        query = {"role": "teacher", "admin_id": current_user.id}
        cursor = db.users.find(query)
        async for doc in cursor:
            items.append(_serialize_user(doc))
    else:  # super_admin
        query = {"role": "school_admin"}
        if role:
            if role != "school_admin":
                return {"items": []}
        cursor = db.users.find(query)
        async for doc in cursor:
            items.append(_serialize_user(doc))
    return {"items": items}


@router.put("/{user_id}", summary="更新用户（管理员）")
async def update_user(
    user_id: str,
    payload: UserUpdatePayload,
    db: PostgresCompatDatabase = Depends(get_database),
    current_user: UserSchema = Depends(get_current_admin),
):
    doc = await db.users.find_one({"_id": user_id}) or await db.users.find_one({"_id": {"$eq": user_id}})
    if not doc:
        # ObjectId 字符串兼容
        try:
            from bson import ObjectId

            doc = await db.users.find_one({"_id": ObjectId(user_id)})
        except Exception:
            doc = None
    if not doc:
        raise HTTPException(status_code=404, detail="用户不存在")

    target_role = doc.get("role")
    if current_user.role == "school_admin":
        if target_role != "teacher" or doc.get("admin_id") != current_user.id:
            raise HTTPException(status_code=403, detail="无权操作该用户")
    else:
        if target_role != "school_admin":
            raise HTTPException(status_code=403, detail="超级管理员仅管理学校管理员")

    update_fields = {}
    if payload.name is not None:
        update_fields["name"] = payload.name
    if payload.email is not None:
        update_fields["email"] = payload.email
    if current_user.role == "super_admin" and payload.is_active is not None:
        update_fields["is_active"] = payload.is_active
    if current_user.role == "super_admin" and target_role == "school_admin":
        # 允许调整学校归属
        if payload.school_id is not None:
            update_fields["school_id"] = payload.school_id
        if payload.school_name is not None:
            update_fields["school_name"] = payload.school_name
    if current_user.role == "super_admin" and payload.password:
        update_fields["password_hash"] = UserSchema.hash_password(payload.password)
    if payload.is_active is not None:
        update_fields["is_active"] = payload.is_active
    if payload.password and current_user.role == "school_admin":
        update_fields["password_hash"] = UserSchema.hash_password(payload.password)
    if not update_fields:
        return _serialize_user(doc)

    update_fields["updated_at"] = datetime.utcnow()
    await db.users.update_one({"_id": doc["_id"]}, {"$set": update_fields})
    doc.update(update_fields)
    return _serialize_user(doc)


@router.delete("/{user_id}", summary="删除用户（管理员）")
async def delete_user(
    user_id: str,
    db: PostgresCompatDatabase = Depends(get_database),
    current_user: UserSchema = Depends(get_current_admin),
):
    doc = await db.users.find_one({"_id": user_id}) or await db.users.find_one({"_id": {"$eq": user_id}})
    if not doc:
        try:
            from bson import ObjectId

            doc = await db.users.find_one({"_id": ObjectId(user_id)})
        except Exception:
            doc = None
    if not doc:
        raise HTTPException(status_code=404, detail="用户不存在")

    target_role = doc.get("role")
    if target_role == "super_admin":
        raise HTTPException(status_code=403, detail="不可删除超级管理员")
    if current_user.role == "school_admin":
        if target_role != "teacher" or doc.get("admin_id") != current_user.id:
            raise HTTPException(status_code=403, detail="无权操作该用户")
    else:
        if target_role != "school_admin":
            raise HTTPException(status_code=403, detail="超级管理员仅管理学校管理员")

    await db.users.delete_one({"_id": doc["_id"]})
    return {"message": "删除成功"}
