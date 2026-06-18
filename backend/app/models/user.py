"""
用户模型 - 支持家长和管理员两种角色
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from datetime import datetime, timedelta
from bson import ObjectId
try:
    import bcrypt  # type: ignore
except Exception:  # pragma: no cover
    bcrypt = None
from jose import JWTError, jwt

from app.core.config import settings


class UserSchema(BaseModel):
    """用户数据模型"""
    id: Optional[str] = Field(default=None, alias="_id")
    
    # 通用字段
    phone: str = Field(..., description="手机号（唯一标识）")
    password_hash: Optional[str] = Field(default="", description="加密后的密码")
    role: Literal["parent", "teacher", "school_admin", "super_admin"] = Field(..., description="用户角色")
    is_active: bool = Field(default=True, description="账号是否激活")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None
    
    # 通用字段（用于前端显示）
    name: Optional[str] = Field(default=None, description="用户姓名")
    email: Optional[str] = Field(default=None, description="邮箱")
    school_id: Optional[str] = Field(default=None, description="学校标识（管理员）")
    school_name: Optional[str] = Field(default=None, description="学校名称（管理员）")
    admin_id: Optional[str] = Field(default=None, description="老师绑定的管理员 ID")
    
    # 家长专属字段
    parent_name: Optional[str] = Field(default=None, description="家长姓名")
    student_name: Optional[str] = Field(default=None, description="学生姓名")
    student_age: Optional[int] = Field(default=None, description="学生年龄")
    grade_applying: Optional[str] = Field(default=None, description="申请年级")
    anonymous_id: Optional[str] = Field(default=None, description="匿名访客ID")
    is_guest: bool = Field(default=False, description="是否访客账号")
    
    class Config:
        populate_by_name = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }
        json_schema_extra = {
            "example": {
                "phone": "13800138000",
                "role": "parent",
                "parent_name": "张三",
                "student_name": "张小明",
                "student_age": 10,
                "grade_applying": "G6"
            }
        }
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """验证手机号格式"""
        # 允许特殊账号 admin/root
        if v in ("admin", "root"):
            return v
        if not v.isdigit() or len(v) != 11:
            raise ValueError('手机号必须是11位数字')
        return v
    
    @field_validator('student_age')
    @classmethod
    def validate_age(cls, v: Optional[int]) -> Optional[int]:
        """验证年龄"""
        if v is not None and (v < 3 or v > 18):
            raise ValueError('学生年龄必须在3-18岁之间')
        return v
    
    @staticmethod
    def hash_password(password: str) -> str:
        """密码加密"""
        try:
            return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        except Exception:
            # 开发环境缺少 bcrypt 时的降级（仅用于本地调试）
            return f"plain:{password}"
    
    def verify_password(self, password: str) -> bool:
        """验证密码"""
        # 如果没有密码哈希，返回False
        if not self.password_hash:
            return False

        # 明文标记（仅本地调试降级）
        if self.password_hash.startswith("plain:"):
            return password == self.password_hash.split("plain:", 1)[1]

        try:
            return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
        except Exception:
            # 密码哈希格式错误或缺少依赖时，拒绝登录
            return False
    
    def create_access_token(self) -> str:
        """生成 JWT access token"""
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        # 使用 phone 作为唯一标识（因为 _id 可能为 None）
        to_encode = {
            "sub": self.phone,
            "role": self.role,
            "exp": expire
        }
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str) -> Optional[dict]:
        """验证 JWT token 并返回 payload"""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            return payload
        except JWTError:
            return None
    
    def to_dict(self, exclude_sensitive: bool = True) -> dict:
        """转换为字典（可选择排除敏感信息）"""
        data = self.model_dump(by_alias=True, exclude_none=True)
        if exclude_sensitive:
            data.pop('password_hash', None)
        return data


class UserCreateRequest(BaseModel):
    """用户注册请求"""
    phone: str
    password: str = Field(..., min_length=6, description="密码至少6位")
    role: Literal["parent", "teacher", "school_admin", "super_admin"] = "parent"
    
    # 家长注册字段
    parent_name: Optional[str] = None
    student_name: Optional[str] = None
    student_age: Optional[int] = None
    grade_applying: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "phone": "13800138000",
                "password": "123456",
                "role": "parent",
                "parent_name": "张三",
                "student_name": "张小明"
            }
        }


class UserLoginRequest(BaseModel):
    """用户登录请求"""
    phone: str
    password: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "phone": "13800138000",
                "password": "123456"
            }
        }


class UserResponse(BaseModel):
    """用户响应（不包含敏感信息）"""
    id: str = Field(..., alias="_id")
    phone: str
    role: str
    is_active: bool
    created_at: datetime
    school_id: Optional[str] = None
    school_name: Optional[str] = None
    admin_id: Optional[str] = None
    
    # 家长信息
    parent_name: Optional[str] = None
    student_name: Optional[str] = None
    student_age: Optional[int] = None
    grade_applying: Optional[str] = None
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TokenResponse(BaseModel):
    """JWT Token 响应"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
