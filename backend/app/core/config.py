from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Any
from pathlib import Path
import json
import logging
from copy import deepcopy

logger = logging.getLogger(__name__)

DEFAULT_WECHAT_ADVISORS = [
    {
        "campus": "浦东",
        "teacher_name": "Sophia Liu",
        "wechat_id": "wxid_pudong_advisor",
        "qr_image": "pudong.png",
        "contact_phone": "13800001111",
    },
    {
        "campus": "浦西",
        "teacher_name": "Daniel Chen",
        "wechat_id": "wxid_puxi_advisor",
        "qr_image": "puxi.png",
        "contact_phone": "13800002222",
    },
    {
        "campus": "临港",
        "teacher_name": "Emily Zhang",
        "wechat_id": "wxid_lingang_advisor",
        "qr_image": "lingang.png",
        "contact_phone": "13800003333",
    },
]


class Settings(BaseSettings):
    """
    应用配置类
    
    所有配置项都可以通过环境变量或 .env 文件设置
    优先级: 环境变量 > .env 文件 > 默认值
    """
    
    # ========== 数据库配置 ==========
    # PostgreSQL 连接字符串
    # 开发环境示例: postgresql://postgres:password123@localhost:5436/General_ageng_admissions
    # ⚠️ 生产环境必须通过环境变量设置，不要使用默认值
    POSTGRES_HOST_PORT: int = 5436
    POSTGRES_URL: str
    POSTGRES_SSL: bool = False
    
    # 数据库名称
    POSTGRES_DB: str = "General_ageng_admissions"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "password123"
    DB_NAME: str = "General_ageng_admissions"

    # ========== Docker / 部署配置 ==========
    SERVER_DOCKER_REGISTRY: str | None = None
    SERVER_DOCKER_NAMESPACE: str = "General_ageng"
    BACKEND_IMAGE_NAME: str = "General_ageng-backend"
    BACKEND_IMAGE_TAG: str = "latest"
    FRONTEND_IMAGE_NAME: str = "General_ageng-frontend"
    FRONTEND_IMAGE_TAG: str = "latest"
    BACKEND_PULL_POLICY: str = "always"
    FRONTEND_PULL_POLICY: str = "always"
    BACKEND_HOST_PORT: int = 9008
    FRONTEND_HOST_PORT: int = 8006
    MINIO_API_PORT: int = 9002
    MINIO_CONSOLE_PORT: int = 9004

    # ========== LLM 配置 ==========
    LLM_PROVIDER: str = "qwen"
    LANGCHAIN_CHAT_MODEL: str = "qwen3-max"
    LANGCHAIN_EXTRACTION_MODEL: str | None = None
    LANGCHAIN_CHAT_TEMPERATURE: float = 0.2
    LANGCHAIN_CHAT_SYSTEM_PROMPT: str | None = None
    OPENAI_API_KEY: str | None = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    QWEN_API_KEY: str | None = None
    QWEN_API_BASE: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_API_BASE: str = "https://api.anthropic.com"
    ANTHROPIC_VERSION: str = "2023-06-01"
    EMBEDDING_PROVIDER: str = "qwen"
    EMBEDDING_MODEL: str = "text-embedding-v4"

    # ========== 知识库配置 ==========
    KNOWLEDGE_BASE_DIR: str = "rag/data/knowledge_base"
    CHROMA_PERSIST_DIR: str = "rag/data/chroma/vector_store"
    CHROMA_COLLECTION_NAME: str = "General_ageng_kb"
    CHROMA_TOP_K: int = 4
    PARENT_CHUNK_SIZE: int = 1200
    PARENT_CHUNK_OVERLAP: int = 120
    CHILD_CHUNK_SIZE: int = 320
    CHILD_CHUNK_OVERLAP: int = 40
    PROMPT_CACHE_TTL: int = 10800  # 默认 3 小时

    # ========== 知识库（RAG 管理） ==========
    RAG_TMP_DIR: str = "rag/data/tmp_uploads"
    RAG_BUCKET: str = "fy-rag-docs"
    RAG_MINIO_ENDPOINT: str | None = None
    RAG_MINIO_ACCESS_KEY: str | None = None
    RAG_MINIO_SECRET_KEY: str | None = None
    RAG_MINIO_SECURE: bool = False
    RAG_BM25_CACHE: str = "rag/data/rag/bm25_store.json"
    RAG_CHROMA_DIR: str = "rag/data/rag/chroma"
    RAG_USE_ASYNC_DEFAULT: bool = True
    REDIS_HOST_PORT: int = 6396
    RAG_REDIS_URL: str | None = None
    RAG_EMBED_MODEL: str = "text-embedding-v4"
    RAG_IMAGE_OCR_MODEL: str = "qwen3-vl-plus"

    # Tencent API
    TENCENT_SECRET_ID: str | None = None
    TENCENT_SECRET_KEY: str | None = None
    TENCENT_REGION: str = "ap-shanghai"

    # Security AI provider toggle
    SECURITY_LLM_ENABLED: bool = False
    SECURITY_LLM_ENDPOINT: str | None = None  # e.g., https://aigate.shinyinfo.com.cn:9443/compatible-mode/v1/chat/completions
    SECURITY_LLM_APIKEY: str | None = None
    SECURITY_LLM_MODEL: str = "qwen3-max"

    # ========== LangSmith 追踪配置 ==========
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_ENDPOINT: str | None = None
    LANGCHAIN_API_KEY: str | None = None
    LANGCHAIN_PROJECT: str | None = None

    # ========== SMTP & Email 配置 ==========
    SMTP_HOST: str = "smtp.qq.com"
    SMTP_PORT: int = 465
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_SENDER_NAME: str = "我校招生办"

    # ========== 后端服务配置 ==========
    # 服务监听地址
    BACKEND_HOST: str = "127.0.0.1"
    
    # 服务监听端口
    BACKEND_PORT: int = 9008

    # ========== JWT 认证配置 ==========
    # ⚠️ JWT 密钥 - 生产环境必须使用随机生成的密钥！
    # 生成方式: openssl rand -hex 32 或 python backend/scripts/generate_secret_key.py
    SECRET_KEY: str
    
    # JWT 算法
    ALGORITHM: str = "HS256"
    
    # Token 过期时间（分钟）
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7天 = 7 * 24 * 60

    # ========== CORS 配置 ==========
    # 允许的跨域来源（支持 JSON 数组字符串或 Python List）
    CORS_ORIGINS: List[str] | str = [
        "http://localhost:8006",
        "http://127.0.0.1:8006",
    ]

    # ========== 企业微信配置 ==========
    WECHAT_QR_BASE_URL: str = "/static/wecom_qr"
    WECHAT_ADVISORS: List[dict] | str = deepcopy(DEFAULT_WECHAT_ADVISORS)
    WECOM_TOKEN: str | None = None
    WECOM_ENCODING_AES_KEY: str | None = None
    WECOM_RECEIVE_ID: str | None = None
    EXTRA_CORS_ORIGINS: str | None = None

    # ========== 应用配置 ==========
    # ⚠️ 调试模式（生产环境必须设置为 False）
    DEBUG: bool = True
    
    # 日志级别
    LOG_LEVEL: str = "INFO"

    # ========== 业务配置 ==========
    # 意向评分阈值（超过此分数自动创建线索）
    INTENT_SCORE_THRESHOLD: int = 60
    
    # 会话自动归档时间（天）
    AUTO_ARCHIVE_DAYS: int = 90
    
    # 线索自动跟进提醒时间（天）
    FOLLOW_UP_REMINDER_DAYS: int = 3

    # ========== 尘锋 Agent 接入 ==========
    CF_AGENT_BASE_URL: str = "https://qw-openapi-tx.dustess.com"
    CF_AGENT_CLIENT_ID: str | None = None
    CF_AGENT_CLIENT_SECRET: str | None = None
    CF_AGENT_CALLBACK_TOKEN: str | None = None
    CF_AGENT_ENCODING_AES_KEY: str | None = None
    CF_AGENT_RECEIVE_ID: str | None = None
    CF_AGENT_USER_ID: str | None = None
    CF_AGENT_SCRM_ACCOUNT_ID: str | None = None
    CF_AGENT_TEST_CHAT_ID: str | None = None
    CF_AGENT_TEST_QW_USER_ID: str | None = None
    CF_AGENT_TEST_TARGET_IDS: List[str] | str | None = None

    @field_validator('DEBUG', mode='before')
    @classmethod
    def validate_debug(cls, v: Any) -> bool:
        """验证 DEBUG 字段，支持多种格式"""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            # 处理字符串格式的 DEBUG 值
            v_lower = v.lower().strip()
            if v_lower in ('true', '1', 'yes', 'on'):
                return True
            elif v_lower in ('false', '0', 'no', 'off'):
                return False
            else:
                # 对于其他字符串值（如 'WARN', 'INFO' 等），默认为 False
                logger.warning(f"DEBUG 环境变量值 '{v}' 无法解析为布尔值，使用默认值 False")
                return False
        if isinstance(v, int):
            return bool(v)
        # 其他类型默认为 False
        logger.warning(f"DEBUG 环境变量类型 {type(v)} 无法解析，使用默认值 False")
        return False

    class Config:
        # 统一读取项目根目录 .env
        project_root = Path(__file__).resolve().parents[3]
        env_file = str(project_root / ".env")
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"
    
    def __init__(self, **kwargs):
        """初始化配置并进行安全检查"""
        super().__init__(**kwargs)

        self.LLM_PROVIDER = (self.LLM_PROVIDER or "qwen").lower()
        
        # 处理 CORS_ORIGINS（支持 JSON 字符串格式）
        if isinstance(self.CORS_ORIGINS, str):
            try:
                self.CORS_ORIGINS = json.loads(self.CORS_ORIGINS)
            except json.JSONDecodeError:
                logger.warning(f"CORS_ORIGINS 格式错误，使用默认值")
                self.CORS_ORIGINS = [
                    "http://localhost:8006",
                    "http://127.0.0.1:8006",
                ]

        if isinstance(self.WECHAT_ADVISORS, str):
            try:
                self.WECHAT_ADVISORS = json.loads(self.WECHAT_ADVISORS)
            except json.JSONDecodeError:
                logger.warning("WECHAT_ADVISORS 格式错误，使用默认值")
                self.WECHAT_ADVISORS = deepcopy(DEFAULT_WECHAT_ADVISORS)

        if not self.WECHAT_ADVISORS:
            self.WECHAT_ADVISORS = deepcopy(DEFAULT_WECHAT_ADVISORS)

        if self.EXTRA_CORS_ORIGINS:
            extra = []
            try:
                extra = json.loads(self.EXTRA_CORS_ORIGINS)
            except json.JSONDecodeError:
                extra = [origin.strip() for origin in self.EXTRA_CORS_ORIGINS.split(",") if origin.strip()]
            if extra:
                self.CORS_ORIGINS.extend(o for o in extra if o not in self.CORS_ORIGINS)

        if isinstance(self.CF_AGENT_TEST_TARGET_IDS, str):
            try:
                self.CF_AGENT_TEST_TARGET_IDS = json.loads(self.CF_AGENT_TEST_TARGET_IDS)
            except json.JSONDecodeError:
                self.CF_AGENT_TEST_TARGET_IDS = [
                    target.strip()
                    for target in self.CF_AGENT_TEST_TARGET_IDS.split(",")
                    if target.strip()
                ]
        
        # 安全检查
        self._validate_security_settings()
    
    def _validate_security_settings(self):
        """验证安全配置"""
        warnings = []
        
        # 检查 SECRET_KEY
        if self.SECRET_KEY == "your-secret-key-please-change-me-use-openssl-rand-hex-32":
            warnings.append("⚠️  使用了默认的 SECRET_KEY！生产环境必须修改！")
        
        if len(self.SECRET_KEY) < 32:
            warnings.append("⚠️  SECRET_KEY 长度过短（建议至少 32 个字符）")
        
        if self.LLM_PROVIDER == "openai" and not self.OPENAI_API_KEY:
            warnings.append("⚠️  OPENAI_API_KEY 未设置，AI 功能将无法使用")
        if self.LLM_PROVIDER == "ollama" and not self.OLLAMA_BASE_URL:
            warnings.append("⚠️  OLLAMA_BASE_URL 未设置，默认为 http://localhost:11434")
        if self.LLM_PROVIDER == "qwen" and not self.QWEN_API_KEY:
            warnings.append("⚠️  QWEN_API_KEY 未设置，无法调用线上通义千问模型")
        if self.LLM_PROVIDER == "anthropic" and not self.ANTHROPIC_API_KEY:
            warnings.append("⚠️  ANTHROPIC_API_KEY 未设置，无法调用 Anthropic 兼容接口")
        if self.LLM_PROVIDER not in {"openai", "ollama", "qwen", "anthropic"}:
            warnings.append(f"⚠️  不支持的 LLM_PROVIDER: {self.LLM_PROVIDER}")
        
        if not self.SMTP_USER or not self.SMTP_PASSWORD:
            warnings.append("⚠️  SMTP_USER 或 SMTP_PASSWORD 未设置，邮件功能将无法使用")
        
        # 检查 DEBUG 模式
        if not self.DEBUG and self.LOG_LEVEL == "DEBUG":
            warnings.append("⚠️  生产环境不建议使用 DEBUG 日志级别")
        
        # 输出警告
        if warnings:
            logger.warning("=" * 60)
            logger.warning("配置安全检查发现以下问题:")
            for warning in warnings:
                logger.warning(f"  {warning}")
            logger.warning("=" * 60)
            
            # 生产环境严格检查
            if not self.DEBUG:
                if self.SECRET_KEY == "your-secret-key-please-change-me-use-openssl-rand-hex-32":
                    raise ValueError(
                        "❌ 生产环境禁止使用默认 SECRET_KEY！\n"
                        "请通过环境变量设置: export SECRET_KEY=$(openssl rand -hex 32)"
                    )


# 创建全局配置实例
try:
    settings = Settings()
    logger.info("✅ 配置加载成功")
except Exception as e:
    logger.error(f"❌ 配置加载失败: {str(e)}")
    logger.error("请检查 .env 文件是否存在，或必要的环境变量是否已设置")
    logger.error("当前统一读取项目根目录 .env")
    logger.error("可参考项目根目录 .env.example 创建配置文件")
    raise
