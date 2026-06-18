"""命令行工具：检索知识库并打印召回结果。"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Sequence

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.knowledge_base_service import get_knowledge_base_service


def format_document(idx: int, page_content: str, metadata: dict) -> str:
    lines = [
        f"[{idx}] 来源: {metadata.get('source', '未知')}",
        f"问题: {metadata.get('question') or '—'}",
        "内容:",
        page_content,
        "-" * 60,
    ]
    return "\n".join(lines)


async def search(query: str, top_k: int) -> None:
    service = get_knowledge_base_service()
    docs: Sequence = await service.asearch(query, k=top_k)
    if not docs:
        print("⚠️ 未检索到任何结果，请检查查询词或知识库内容。")
        return
    for idx, doc in enumerate(docs, 1):
        print(format_document(idx, getattr(doc, "page_content", ""), dict(getattr(doc, "metadata", {}) or {})))


def main() -> None:
    parser = argparse.ArgumentParser(description="检索 Chroma 知识库，快速查看召回结果。")
    parser.add_argument("query", help="查询内容")
    parser.add_argument("--top-k", type=int, default=4, help="返回的结果条数")
    args = parser.parse_args()

    asyncio.run(search(args.query, args.top_k))


if __name__ == "__main__":
    main()
