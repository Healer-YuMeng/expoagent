"""
依赖注入模块
提供通用的依赖项，如当前用户获取、权限检查等
"""
from typing import Optional
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt

from app.db import PostgresCompatDatabase, get_database
from app.models.user import UserSchema
from app.core.config import settings

# HTTP Bearer Token 安全方案
security = HTTPBearer()


def create_access_token(data: dict) -> str:
    """
    生成 JWT access token（用于测试和独立使用）
    
    Args:
        data: 要编码的数据字典
        
    Returns:
        str: JWT token
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """
    解码 JWT access token（用于测试和独立使用）
    
    Args:
        token: JWT token
        
    Returns:
        Optional[dict]: 解码后的 payload，如果失败返回 None
    """
    return UserSchema.verify_token(token)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: PostgresCompatDatabase = Depends(get_database)
) -> UserSchema:
    """
    从 JWT Token 获取当前用户
    
    Args:
        credentials: HTTP Bearer Token
        db: 数据库连接
        
    Returns:
        UserSchema: 当前用户对象
        
    Raises:
        HTTPException: Token 无效或用户不存在
    """
    token = credentials.credentials
    
    # 验证 Token 并获取 phone
    payload = UserSchema.verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    phone = payload.get("sub")
    if not phone:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 从数据库获取用户（使用 phone 而不是 _id）
    user_dict = await db.users.find_one({"phone": phone})
    if not user_dict:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 转换 ObjectId 为字符串
    if "_id" in user_dict:
        user_dict["_id"] = str(user_dict["_id"])
    
    user = UserSchema(**user_dict)
    
    # 检查用户是否被禁用
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用"
        )
    
    return user


async def get_current_parent(
    current_user: UserSchema = Depends(get_current_user)
) -> UserSchema:
    """
    获取当前家长用户（角色验证）
    
    Args:
        current_user: 当前用户
        
    Returns:
        UserSchema: 家长用户对象
        
    Raises:
        HTTPException: 用户不是家长角色
    """
    if current_user.role != "parent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要家长权限"
        )
    return current_user



async def get_current_teacher(
    current_user: UserSchema = Depends(get_current_user)
) -> UserSchema:
    """
    兼容旧命名：教师/管理员/超级管理员均视为“老师端”可访问
    """
    if current_user.role not in ("teacher", "school_admin", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要老师权限"
        )
    return current_user


async def get_current_admin(
    current_user: UserSchema = Depends(get_current_user)
) -> UserSchema:
    """
    学校管理员或超级管理员
    """
    if current_user.role not in ("school_admin", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return current_user


async def get_current_super_admin(
    current_user: UserSchema = Depends(get_current_user)
) -> UserSchema:
    """
    仅超级管理员
    """
    if current_user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要超级管理员权限"
        )
    return current_user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: PostgresCompatDatabase = Depends(get_database)
) -> Optional[UserSchema]:
    """
    获取可选的当前用户（不强制要求认证）
    用于某些可以匿名访问但登录后有额外功能的接口
    
    Args:
        credentials: HTTP Bearer Token（可选）
        db: 数据库连接
        
    Returns:
        Optional[UserSchema]: 用户对象或 None
    """
    if not credentials:
        return None
    
    try:
        token = credentials.credentials
        payload = UserSchema.verify_token(token)
        if not payload:
            return None
        
        phone = payload.get("sub")
        if not phone:
            return None
        
        user_dict = await db.users.find_one({"phone": phone})
        if not user_dict:
            return None
        
        user = UserSchema(**user_dict)
        if not user.is_active:
            return None
        
        return user
    except Exception:
        return None
