"""
展会智能助手后端主应用
"""
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.db import connect_to_postgres, close_postgres_connection, init_db_indexes
from app.core.config import settings
from app.db import ensure_default_admin_accounts

# 导入所有路由
from app.routers import agent, assistants, auth, parent, leads, teacher, wecom, docs, prompts, users

# 配置日志过滤器，减少 /metrics 端点的日志噪音
class MetricsFilter(logging.Filter):
    def filter(self, record):
        # 过滤掉 /metrics 端点的访问日志
        return not (hasattr(record, 'getMessage') and 
                   'GET /metrics' in record.getMessage())

# 应用日志过滤器到 uvicorn 的访问日志
uvicorn_logger = logging.getLogger("uvicorn.access")
uvicorn_logger.addFilter(MetricsFilter())

app = FastAPI(
    title="展会智能助手后台管理系统 API",
    description="展会智能体管理平台后端 API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 静态资源（企微二维码等）
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    await connect_to_postgres()
    await init_db_indexes()
    # 创建默认管理员账号（admin/admin, root/root）
    try:
        await ensure_default_admin_accounts()
    except Exception as exc:
        print(f"⚠️ 默认管理员创建失败: {exc}")
    print(f"✅ 应用启动成功")
    print(f"📖 API 文档: http://{settings.BACKEND_HOST}:{settings.BACKEND_PORT}/docs")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    await close_postgres_connection()
    print("👋 应用已关闭")


# 注册路由
app.include_router(auth.router)
app.include_router(agent.router)
app.include_router(parent.router)
app.include_router(leads.router)
app.include_router(teacher.router)
app.include_router(wecom.router)
app.include_router(docs.router)
app.include_router(prompts.router)
app.include_router(assistants.router)
app.include_router(users.router)


@app.get("/", tags=["系统"])
def root():
    """根路径"""
    return {
        "message": "欢迎使用 展会智能助手后台管理系统 API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health", tags=["系统"])
def health_check():
    """健康检查"""
    return {"status": "ok", "message": "系统运行正常"}


@app.get("/metrics", tags=["系统"])
def metrics():
    """系统指标端点（防止404错误）"""
    return {
        "status": "ok",
        "service": "展会智能助手",
        "version": "1.0.0",
        "uptime": "运行中"
    }
