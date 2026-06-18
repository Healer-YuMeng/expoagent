#!/usr/bin/env python3
"""
删除 PostgreSQL 中早期 Mongo 兼容迁移遗留的 mongo_* 旧表。

使用方法：
    python scripts/drop_legacy_mongo_tables.py
"""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.db import connect_to_postgres, close_postgres_connection, drop_legacy_mongo_tables


async def main() -> int:
    await connect_to_postgres()
    try:
        dropped = await drop_legacy_mongo_tables()
        if dropped:
            print("已删除旧表:")
            for table_name in dropped:
                print(f"  - {table_name}")
        else:
            print("未发现需要删除的 mongo_* 旧表")
        return 0
    finally:
        await close_postgres_connection()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
