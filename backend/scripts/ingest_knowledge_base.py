"""将 Markdown 问答知识库入库到 Chroma。"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import List

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from langchain_core.documents import Document

from app.core.config import settings
from app.services.knowledge_base_service import get_knowledge_base_service

logger = logging.getLogger(__name__)


QA_PATTERN = re.compile(r"^Q[:：](.+?)$", re.IGNORECASE)
ANSWER_PATTERN = re.compile(r"^A[:：](.+?)$", re.IGNORECASE)
COMPACT_DELIMITER = re.compile(r"\n?&&&\s*", re.MULTILINE)


def _parse_compact_qa(text: str, source: Path) -> List[Document]:
    """解析 `问题***回答` 形式的一问一答内容。"""

    docs: List[Document] = []
    current_category: str | None = None

    for block in COMPACT_DELIMITER.split(text):
        content = block.strip()
        if not content:
            continue

        if content.startswith("#"):
            heading = content.lstrip("#").strip()
            if heading:
                current_category = heading
            continue

        if "***" not in content:
            continue

        question_part, answer_part = content.split("***", 1)
        question = question_part.strip()
        answer = answer_part.strip()
        if not question or not answer:
            continue

        metadata = {
            "source": str(source),
            "question": question,
        }
        if current_category:
            metadata["category"] = current_category

        docs.append(
            Document(
                page_content=f"问题：{question}\n回答：{answer}",
                metadata=metadata,
            )
        )

    return docs


def parse_markdown_qa(path: Path) -> List[Document]:
    """解析一问一答 Markdown 文档，生成 LangChain Document 列表。"""

    text = path.read_text(encoding="utf-8")
    if "***" in text:
        return _parse_compact_qa(text, path)
    lines = text.splitlines()

    current_category: str | None = None
    docs: List[Document] = []

    i = 0
    total_lines = len(lines)
    while i < total_lines:
        raw_line = lines[i]
        stripped = raw_line.strip()

        if not stripped:
            i += 1
            continue

        if stripped.startswith("#"):
            # 记录最近的标题，方便作为 metadata
            heading = stripped.lstrip("#").strip()
            if heading:
                current_category = heading
            i += 1
            continue

        q_match = QA_PATTERN.match(stripped)
        if q_match:
            question = q_match.group(1).strip()
            i += 1
            answer_lines: list[str] = []

            while i < total_lines:
                candidate = lines[i]
                candidate_stripped = candidate.strip()

                if not candidate_stripped:
                    answer_lines.append("")
                    i += 1
                    continue

                if candidate_stripped.startswith("#"):
                    break

                if QA_PATTERN.match(candidate_stripped):
                    break

                a_match = ANSWER_PATTERN.match(candidate_stripped)
                if a_match:
                    answer_lines.append(a_match.group(1).strip())
                else:
                    answer_lines.append(candidate.rstrip())
                i += 1

            answer = "\n".join(part for part in answer_lines).strip()
            if not answer:
                logger.warning("文件 %s 中的问题 `%s` 未找到答案，已跳过", path, question)
                continue

            page_content = f"问题：{question}\n回答：{answer}"
            metadata = {
                "source": str(path),
                "question": question,
            }
            if current_category:
                metadata["category"] = current_category

            docs.append(Document(page_content=page_content, metadata=metadata))
            continue

        i += 1

    return docs


def load_documents_from_dir(root: Path) -> List[Document]:
    documents: List[Document] = []
    for path in sorted(root.rglob("*.md")):
        documents.extend(parse_markdown_qa(path))
    return documents


def _resolve_path(path_like: Path) -> Path:
    if path_like.is_absolute():
        return path_like
    parts = path_like.parts
    if parts and parts[0] == "backend":
        return PROJECT_ROOT / path_like
    return BACKEND_ROOT / path_like


def ingest_knowledge_base(root: Path) -> None:
    service = get_knowledge_base_service()
    docs = load_documents_from_dir(root)
    if not docs:
        logger.warning("未在 %s 下找到任何问答文档，知识库未更新", root)
        return

    service.add_documents(docs)
    logger.info("成功入库 %s 条问答文档", len(docs))


def main() -> None:
    parser = argparse.ArgumentParser(description="将 Markdown 问答知识库导入 Chroma 向量库")
    parser.add_argument(
        "--root",
        default=settings.KNOWLEDGE_BASE_DIR,
        help="知识库 Markdown 根目录 (默认: %(default)s)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    root = _resolve_path(Path(args.root))
    if not root.exists():
        logger.error("知识库目录 %s 不存在，请先创建并放入 Markdown 文件", root)
        return

    ingest_knowledge_base(root)


if __name__ == "__main__":
    main()
