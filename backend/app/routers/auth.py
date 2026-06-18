"""
认证路由
处理用户登录、注册等认证相关接口
"""
import logging
import secrets
from datetime import datetime
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.db import PostgresCompatDatabase, get_database
from app.models.user import UserSchema, UserCreateRequest
from app.core.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["认证"])


# ========== 请求/响应模型 ==========

class LoginRequest(BaseModel):
    """通用登录请求"""
    phone: str = Field(..., description="手机号或账号", pattern=r"(^1[3-9]\d{9}$)|^(admin|root)$")
    password: str = Field(..., description="密码", min_length=3)


class LoginResponse(BaseModel):
    """登录响应"""
    access_token: str = Field(..., description="访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    user: dict = Field(..., description="用户信息")


class AnonymousSessionRequest(BaseModel):
    """匿名访客会话请求"""
    anonymous_id: Optional[str] = Field(default=None, description="客户端匿名ID")


class AnonymousSessionResponse(BaseModel):
    """匿名访客会话响应"""
    access_token: str = Field(..., description="访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    anonymous_id: str = Field(..., description="匿名访客ID")
    user: dict = Field(..., description="用户信息")


class UserInfoResponse(BaseModel):
    """用户信息响应"""
    id: str
    phone: str
    name: Optional[str] = None
    role: str
    email: Optional[str] = None
    is_active: bool
    created_at: datetime


# ========== API 路由 ==========

@router.post("/register", response_model=LoginResponse, summary="用户注册")
async def register_user(
    request: UserCreateRequest,
    db: PostgresCompatDatabase = Depends(get_database)
):
    """
    用户注册
    
    - 支持家长和管理员注册
    - 手机号不能重复
    - 密码自动加密存储
    """
    phone = request.phone
    
    # 检查手机号是否已存在
    existing_user = await db.users.find_one({"phone": phone})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该手机号已注册，请直接登录"
        )
    
    # 创建新用户
    user = UserSchema(
        phone=phone,
        password_hash=UserSchema.hash_password(request.password),
        role=request.role,
        parent_name=request.parent_name,
        student_name=request.student_name,
        student_age=request.student_age,
        grade_applying=request.grade_applying,
    )
    
    # 保存到数据库
    user_dict = user.model_dump()
    result = await db.users.insert_one(user_dict)
    user.id = str(result.inserted_id)
    
    logger.info(f"新用户注册成功: {phone}, 角色: {user.role}")
    
    display_name = user.parent_name if user.role == "parent" else user.name
    
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user={
            "id": user.id,
            "phone": user.phone,
            "name": display_name or user.phone,
            "role": user.role,
            "email": user.email,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat()
        }
    )


@router.post("/login", response_model=LoginResponse, summary="用户登录")
async def login_user(
    request: LoginRequest,
    db: PostgresCompatDatabase = Depends(get_database)
):
    """
    用户密码登录
    
    - 使用手机号和密码登录
    - 支持家长和管理员角色
    """
    phone = request.phone
    password = request.password
    
    # 查找用户
    user_dict = await db.users.find_one({"phone": phone})
    
    # 若默认 admin/root 不存在，自动创建
    if not user_dict and phone in ("admin", "root"):
        default_role = "school_admin" if phone == "admin" else "super_admin"
        default_name = "默认学校管理员" if phone == "admin" else "默认超级管理员"
        default_school_id = "default_school" if phone == "admin" else None
        default_school_name = "默认学校" if phone == "admin" else None
        user_obj = UserSchema(
            phone=phone,
            password_hash=UserSchema.hash_password(phone),  # 默认密码同账号
            role=default_role,  # type: ignore[arg-type]
            name=default_name,
            school_id=default_school_id,
            school_name=default_school_name,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        await db.users.insert_one(user_obj.model_dump(by_alias=True))
        user_dict = user_obj.model_dump(by_alias=True)
    
    if not user_dict:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="手机号或密码错误"
        )
    
    # 转换 ObjectId 为字符串
    if "_id" in user_dict:
        user_dict["_id"] = str(user_dict["_id"])
    
    user = UserSchema(**user_dict)
    
    # 检查用户是否被禁用
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="该账号已被禁用，请联系管理员"
        )
    
    # 验证密码；admin/root 支持重置为默认同名密码
    if not user.verify_password(password):
        if phone in ("admin", "root") and password == phone:
            # 重置为默认密码
            new_hash = UserSchema.hash_password(password)
            await db.users.update_one({"_id": user_dict.get("_id")}, {"$set": {"password_hash": new_hash}})
            user.password_hash = new_hash
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="手机号或密码错误"
            )
    
    # 生成 JWT Token
    access_token = user.create_access_token()
    
    logger.info(f"用户登录成功: {phone}, 角色: {user.role}")
    
    # 根据角色返回对应的姓名
    display_name = user.parent_name if user.role == "parent" else user.name
    
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user={
            "id": user.id or user.phone,  # 如果 id 为 None，使用 phone
            "phone": user.phone,
            "name": display_name or user.phone,
            "role": user.role,
            "email": user.email,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat(),
            "school_id": user.school_id,
            "school_name": user.school_name,
            "admin_id": user.admin_id,
        }
    )


@router.get("/me", response_model=UserInfoResponse, summary="获取当前用户信息")
async def get_current_user_info(
    current_user: UserSchema = Depends(get_current_user)
):
    """
    获取当前登录用户的详细信息
    
    需要认证：Bearer Token
    """
    # 根据角色返回对应的姓名
    display_name = current_user.parent_name if current_user.role == "parent" else current_user.name
    
    return UserInfoResponse(
        id=current_user.id,
        phone=current_user.phone,
        name=display_name or current_user.phone,
        role=current_user.role,
        email=current_user.email,
        is_active=current_user.is_active,
        created_at=current_user.created_at
    )


@router.post("/logout", summary="登出")
async def logout(current_user: UserSchema = Depends(get_current_user)):
    """
    登出（无状态 JWT，客户端删除 Token 即可）
    
    需要认证：Bearer Token
    """
    logger.info(f"用户登出: {current_user.phone}")
    
    return {"message": "登出成功"}


async def _generate_unique_guest_phone(db: PostgresCompatDatabase) -> str:
    """生成唯一的访客手机号（符合 1[3-9] 开头的11位数字格式）"""
    while True:
        second_digit = secrets.choice("3456789")
        remaining = "".join(secrets.choice("0123456789") for _ in range(9))
        phone = f"1{second_digit}{remaining}"
        existing = await db.users.find_one({"phone": phone})
        if not existing:
            return phone


def _format_user_response(user: UserSchema) -> dict:
    """统一格式化用户信息"""
    display_name = user.parent_name or user.name or user.phone
    return {
        "id": user.id or user.phone,
        "phone": user.phone,
        "name": display_name,
        "role": user.role,
        "email": user.email,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat()
    }


@router.post("/anonymous-session", response_model=AnonymousSessionResponse, summary="创建或恢复匿名访客会话")
async def create_anonymous_session(
    request: AnonymousSessionRequest,
    db: PostgresCompatDatabase = Depends(get_database)
):
    """
    为未登录的家长访客创建或恢复匿名会话

    - 每个访客使用 `anonymous_id` 追踪
    - 自动创建访客账号并返回 JWT，用于后续 API 调用
    """
    now = datetime.utcnow()
    anonymous_id = request.anonymous_id

    if anonymous_id:
        existing_user = await db.users.find_one({"anonymous_id": anonymous_id})
        if existing_user:
            if "_id" in existing_user:
                existing_user["_id"] = str(existing_user["_id"])
            user = UserSchema(**existing_user)
            access_token = user.create_access_token()
            await db.users.update_one(
                {"_id": ObjectId(user.id)},
                {"$set": {"updated_at": now, "last_login": now}}
            )
            return AnonymousSessionResponse(
                access_token=access_token,
                token_type="bearer",
                anonymous_id=anonymous_id,
                user=_format_user_response(user)
            )

    # 创建新的访客账号
    new_anonymous_id = anonymous_id or secrets.token_hex(8)
    phone = await _generate_unique_guest_phone(db)
    user = UserSchema(
        phone=phone,
        role="parent",
        name="访客家长",
        parent_name=None,
        is_active=True,
        created_at=now,
        updated_at=now,
        anonymous_id=new_anonymous_id,
        is_guest=True
    )

    user_dict = user.model_dump(by_alias=True, exclude={"id"})
    result = await db.users.insert_one(user_dict)
    user.id = str(result.inserted_id)

    access_token = user.create_access_token()
    return AnonymousSessionResponse(
        access_token=access_token,
        token_type="bearer",
        anonymous_id=new_anonymous_id,
        user=_format_user_response(user)
    )
