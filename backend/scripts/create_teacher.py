#!/usr/bin/env python3
"""创建固定老师账号脚本（手机号 15164527155）"""
from __future__ import annotations

from datetime import datetime
import asyncio
import sys
from pathlib import Path

# 将 backend 目录加入 Python 模块搜索路径
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db import connect_to_postgres, close_postgres_connection, get_database
from app.models.user import UserSchema


async def main() -> None:
    # 固定参数
    phone = "15164527155"
    name = "test"
    password = "123456"

    await connect_to_postgres()
    db = get_database()

    existing = await db.users.find_one({"phone": phone})
    if existing:
        print(f"⚠️  用户 {phone} 已存在")
        await close_postgres_connection()
        return

    now = datetime.utcnow()
    user = UserSchema(
        phone=phone,
        role="teacher",
        name=name,
        password_hash=UserSchema.hash_password(password),
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    doc = user.model_dump(by_alias=True, exclude={"id"})
    result = await db.users.insert_one(doc)
    print(f"✅ 已创建老师: {phone}, _id={result.inserted_id}")
    await close_postgres_connection()


if __name__ == "__main__":
    asyncio.run(main())
