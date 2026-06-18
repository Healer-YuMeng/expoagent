"""
PostgreSQL compatibility layer with real table schemas.

目标：尽量保持现有 Mongo 风格业务代码不变，
但底层在 PostgreSQL 中为每个 collection 建立真实表与真实字段。
"""

from __future__ import annotations

import json
import logging
import re
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, Optional
from urllib.parse import urlsplit, urlunsplit

import asyncpg
from bson import ObjectId

from .core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    db_type: str
    primary_key: bool = False
    nullable: bool = True
    default_sql: str | None = None
    codec: str | None = None


@dataclass(frozen=True)
class IndexSpec:
    columns: tuple[str, ...]
    unique: bool = False
    name: str | None = None


@dataclass(frozen=True)
class CollectionSchema:
    table_name: str
    columns: tuple[ColumnSpec, ...]
    indexes: tuple[IndexSpec, ...] = field(default_factory=tuple)
    extra_column: str | None = None


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _normalize_scalar(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _parse_datetime_like(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if "T" not in text:
        return value
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return value


def _normalize_datetime_for_compare(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _coerce_comparable(value: Any) -> Any:
    normalized = _normalize_scalar(value)
    normalized = _parse_datetime_like(normalized)
    if isinstance(normalized, datetime):
        normalized = _normalize_datetime_for_compare(normalized)
    return normalized


def _compare_values(left: Any, right: Any) -> int | None:
    left_value = _coerce_comparable(left)
    right_value = _coerce_comparable(right)

    if left_value is None or right_value is None:
        return None

    try:
        if left_value < right_value:
            return -1
        if left_value > right_value:
            return 1
        return 0
    except TypeError:
        left_text = str(left_value)
        right_text = str(right_value)
        if left_text < right_text:
            return -1
        if left_text > right_text:
            return 1
        return 0


def _sortable_key(value: Any) -> tuple[int, Any]:
    normalized = _coerce_comparable(value)
    if normalized is None:
        return (3, "")
    if isinstance(normalized, datetime):
        return (0, normalized.timestamp())
    if isinstance(normalized, (int, float, bool)):
        return (1, float(normalized))
    return (2, str(normalized))


def _normalize_document(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _normalize_document(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize_document(v) for v in value]
    if isinstance(value, tuple):
        return [_normalize_document(v) for v in value]
    return _normalize_scalar(value)


def _json_default(value: Any) -> Any:
    normalized = _normalize_scalar(value)
    if normalized is value:
        return str(value)
    return normalized


def _prepare_jsonb(value: Any) -> str:
    return json.dumps(_normalize_document(value), default=_json_default, ensure_ascii=False)


def _parse_row_doc(row_doc: Any) -> dict[str, Any]:
    if isinstance(row_doc, str):
        return json.loads(row_doc)
    return dict(row_doc)


def _to_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _normalize_datetime_for_compare(value) if value.tzinfo else value
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return _normalize_datetime_for_compare(parsed) if parsed.tzinfo else parsed
        except ValueError:
            return None
    return None


def _to_boolean(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "1", "yes", "on"}:
            return True
        if text in {"false", "0", "no", "off"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return None


def _to_integer(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _split_path(path: str) -> list[str]:
    return [part for part in str(path).split(".") if part]


def _get_path(document: dict[str, Any], path: str) -> tuple[bool, Any]:
    current: Any = document
    for part in _split_path(path):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return False, None
    return True, current


def _set_path(document: dict[str, Any], path: str, value: Any) -> None:
    parts = _split_path(path)
    current: dict[str, Any] = document
    for part in parts[:-1]:
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            current[part] = next_value
        current = next_value
    current[parts[-1]] = _normalize_document(value)


def _match_value(actual: Any, expected: Any) -> bool:
    return _coerce_comparable(actual) == _coerce_comparable(expected)


def _match_field(document: dict[str, Any], field: str, condition: Any) -> bool:
    exists, actual = _get_path(document, field)

    if not isinstance(condition, dict) or not any(str(k).startswith("$") for k in condition.keys()):
        return exists and _match_value(actual, condition)

    for op, expected in condition.items():
        if op == "$eq":
            if not exists or not _match_value(actual, expected):
                return False
        elif op == "$exists":
            if bool(expected) != exists:
                return False
        elif op == "$in":
            if not exists or not any(_match_value(actual, item) for item in expected):
                return False
        elif op == "$regex":
            if not exists:
                return False
            flags = 0
            if "i" in str(condition.get("$options", "")):
                flags |= re.IGNORECASE
            if re.search(str(expected), str(actual), flags) is None:
                return False
        elif op == "$options":
            continue
        elif op == "$gte":
            compare_result = _compare_values(actual, expected)
            if not exists or compare_result is None or compare_result < 0:
                return False
        elif op == "$gt":
            compare_result = _compare_values(actual, expected)
            if not exists or compare_result is None or compare_result <= 0:
                return False
        elif op == "$lte":
            compare_result = _compare_values(actual, expected)
            if not exists or compare_result is None or compare_result > 0:
                return False
        elif op == "$lt":
            compare_result = _compare_values(actual, expected)
            if not exists or compare_result is None or compare_result >= 0:
                return False
        else:
            raise NotImplementedError(f"Unsupported query operator: {op}")
    return True


def _match_query(document: dict[str, Any], query: Optional[dict[str, Any]]) -> bool:
    if not query:
        return True
    for key, condition in query.items():
        if key == "$or":
            if not any(_match_query(document, item) for item in condition):
                return False
            continue
        if key == "$and":
            if not all(_match_query(document, item) for item in condition):
                return False
            continue
        if not _match_field(document, key, condition):
            return False
    return True


def _apply_projection(document: dict[str, Any], projection: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not projection:
        return deepcopy(document)
    include_fields = [key for key, value in projection.items() if value]
    exclude_fields = [key for key, value in projection.items() if not value]
    if include_fields:
        result: dict[str, Any] = {}
        for field in include_fields:
            exists, value = _get_path(document, field)
            if exists:
                _set_path(result, field, value)
        if projection.get("_id", 1) and "_id" in document:
            result["_id"] = document["_id"]
        return result
    result = deepcopy(document)
    for field in exclude_fields:
        if field == "_id":
            result.pop("_id", None)
    return result


def _normalize_sort_spec(sort_spec: Any, direction: Optional[int] = None) -> list[tuple[str, int]]:
    if sort_spec is None:
        return []
    if isinstance(sort_spec, str):
        return [(sort_spec, direction or 1)]
    if isinstance(sort_spec, tuple):
        field, order = sort_spec
        return [(field, int(order))]
    return [(field, int(order)) for field, order in sort_spec]


def _sort_documents(documents: list[dict[str, Any]], sort_spec: list[tuple[str, int]]) -> list[dict[str, Any]]:
    items = list(documents)
    for field, direction in reversed(sort_spec):
        reverse = int(direction) < 0
        items.sort(
            key=lambda doc: (
                0 if _get_path(doc, field)[0] else 1,
                _sortable_key(_get_path(doc, field)[1]),
            ),
            reverse=reverse,
        )
    return items


def _seed_document_from_filter(query: Optional[dict[str, Any]]) -> dict[str, Any]:
    seed: dict[str, Any] = {}
    if not query:
        return seed
    for key, value in query.items():
        if key.startswith("$"):
            continue
        if isinstance(value, dict):
            if "$eq" in value:
                _set_path(seed, key, value["$eq"])
            continue
        _set_path(seed, key, value)
    return seed


def _apply_update(document: dict[str, Any], update: dict[str, Any], *, is_insert: bool) -> dict[str, Any]:
    doc = deepcopy(document)
    if not update:
        return doc

    if "$set" in update:
        for path, value in update["$set"].items():
            _set_path(doc, path, value)

    if is_insert and "$setOnInsert" in update:
        for path, value in update["$setOnInsert"].items():
            _set_path(doc, path, value)

    if "$inc" in update:
        for path, value in update["$inc"].items():
            exists, current = _get_path(doc, path)
            base = current if exists and isinstance(current, (int, float)) else 0
            _set_path(doc, path, base + value)

    if "$push" in update:
        for path, value in update["$push"].items():
            exists, current = _get_path(doc, path)
            items = list(current) if exists and isinstance(current, list) else []
            items.append(_normalize_document(value))
            _set_path(doc, path, items)

    return doc


def _col(
    name: str,
    db_type: str,
    *,
    primary_key: bool = False,
    nullable: bool = True,
    default_sql: str | None = None,
    codec: str | None = None,
) -> ColumnSpec:
    return ColumnSpec(
        name=name,
        db_type=db_type,
        primary_key=primary_key,
        nullable=nullable,
        default_sql=default_sql,
        codec=codec,
    )


def _json_col(name: str, *, default_json: str | None = None, nullable: bool = True) -> ColumnSpec:
    return _col(name, "TEXT", nullable=nullable, default_sql=default_json, codec="json")


COLLECTION_SCHEMAS: dict[str, CollectionSchema] = {
    "users": CollectionSchema(
        table_name="users",
        columns=(
            _col("_id", "TEXT", primary_key=True, nullable=False),
            _col("phone", "TEXT"),
            _col("password_hash", "TEXT"),
            _col("role", "TEXT"),
            _col("is_active", "BOOLEAN", default_sql="TRUE"),
            _col("created_at", "TIMESTAMPTZ"),
            _col("updated_at", "TIMESTAMPTZ"),
            _col("last_login", "TIMESTAMPTZ"),
            _col("name", "TEXT"),
            _col("email", "TEXT"),
            _col("school_id", "TEXT"),
            _col("school_name", "TEXT"),
            _col("admin_id", "TEXT"),
            _col("parent_name", "TEXT"),
            _col("student_name", "TEXT"),
            _col("student_age", "INTEGER"),
            _col("grade_applying", "TEXT"),
            _col("anonymous_id", "TEXT"),
            _col("is_guest", "BOOLEAN", default_sql="FALSE"),
        ),
        indexes=(
            IndexSpec(("phone",), unique=True, name="users_phone_uniq"),
            IndexSpec(("anonymous_id",), unique=True, name="users_anonymous_id_uniq"),
        ),
    ),
    "conversations": CollectionSchema(
        table_name="conversations",
        columns=(
            _col("_id", "TEXT", primary_key=True, nullable=False),
            _col("parent_id", "TEXT"),
            _col("school_id", "TEXT"),
            _col("assistant_id", "TEXT"),
            _json_col("appointment"),
            _col("source_channel", "TEXT"),
            _col("channel_appointment_logged", "BOOLEAN", default_sql="FALSE"),
            _col("wecom_contact_id", "TEXT"),
            _col("created_at", "TIMESTAMPTZ"),
            _col("updated_at", "TIMESTAMPTZ"),
            _col("closed_at", "TIMESTAMPTZ"),
            _col("last_message_at", "TIMESTAMPTZ"),
            _col("message_count", "INTEGER", default_sql="0"),
        ),
    ),
    "conversation_profiles": CollectionSchema(
        table_name="conversation_profiles",
        columns=(
            _col("_id", "TEXT", primary_key=True, nullable=False),
            _json_col("info", default_json="'{}'"),
            _json_col("flags", default_json="'{}'"),
            _col("created_at", "TIMESTAMPTZ"),
            _col("updated_at", "TIMESTAMPTZ"),
        ),
    ),
    "messages": CollectionSchema(
        table_name="messages",
        columns=(
            _col("_id", "TEXT", primary_key=True, nullable=False),
            _col("conversation_id", "TEXT"),
            _col("sender_id", "TEXT"),
            _col("sender_type", "TEXT"),
            _col("sender_name", "TEXT"),
            _col("content", "TEXT"),
            _json_col("metadata"),
            _json_col("attachments", default_json="'[]'"),
            _col("created_at", "TIMESTAMPTZ"),
            _col("is_read", "BOOLEAN", default_sql="FALSE"),
        ),
    ),
    "leads": CollectionSchema(
        table_name="leads",
        columns=(
            _col("_id", "TEXT", primary_key=True, nullable=False),
            _col("parent_id", "TEXT"),
            _col("conversation_id", "TEXT"),
            _col("chat_id", "TEXT"),
            _col("qv_chat_id", "TEXT"),
            _col("is_high_intent", "BOOLEAN", default_sql="FALSE"),
            _col("needs_manual_callback", "BOOLEAN", default_sql="FALSE"),
            _col("source", "TEXT"),
            _col("parent_phone", "TEXT"),
            _col("parent_name", "TEXT"),
            _col("parent_email", "TEXT"),
            _col("campus", "TEXT"),
            _col("school_id", "TEXT"),
            _col("has_foreign_passport", "BOOLEAN", default_sql="FALSE"),
            _col("has_appointment", "BOOLEAN", default_sql="FALSE"),
            _json_col("follow_up_owner"),
            _col("wecom_status", "TEXT"),
            _col("wecom_contact_id", "TEXT"),
            _col("wecom_contact_name", "TEXT"),
            _json_col("wecom_chat_history", default_json="'[]'"),
            _col("student_name", "TEXT"),
            _col("student_age", "INTEGER"),
            _col("grade_applying", "TEXT"),
            _col("student_grade", "TEXT"),
            _col("intent_score", "INTEGER", default_sql="0"),
            _col("summary", "TEXT"),
            _col("en_summary", "TEXT"),
            _json_col("extracted_info"),
            _json_col("follow_up_notes", default_json="'[]'"),
            _json_col("notes", default_json="'[]'"),
            _col("next_follow_up_date", "TIMESTAMPTZ"),
            _col("first_message_at", "TIMESTAMPTZ"),
            _json_col("tags", default_json="'[]'"),
            _json_col("appointment"),
            _col("created_at", "TIMESTAMPTZ"),
            _col("updated_at", "TIMESTAMPTZ"),
        ),
    ),
    "channel_metrics": CollectionSchema(
        table_name="channel_metrics",
        columns=(
            _col("_id", "TEXT", primary_key=True, nullable=False),
            _col("channel", "TEXT"),
            _col("period", "TEXT"),
            _col("date_key", "TEXT"),
            _col("visit_count", "INTEGER", default_sql="0"),
            _col("appointment_count", "INTEGER", default_sql="0"),
            _col("created_at", "TIMESTAMPTZ"),
            _col("updated_at", "TIMESTAMPTZ"),
        ),
        indexes=(IndexSpec(("channel", "period", "date_key"), unique=True, name="channel_metrics_unique"),),
    ),
    "rag_documents": CollectionSchema(
        table_name="rag_documents",
        columns=(
            _col("_id", "TEXT", primary_key=True, nullable=False),
            _col("name", "TEXT"),
            _col("object_name", "TEXT"),
            _col("size", "INTEGER"),
            _col("knowledge_base_id", "TEXT"),
            _col("school_id", "TEXT"),
            _col("admin_id", "TEXT"),
            _col("status", "TEXT"),
            _col("chunk_count", "INTEGER", default_sql="0"),
            _col("created_at", "TIMESTAMPTZ"),
            _col("updated_at", "TIMESTAMPTZ"),
        ),
        indexes=(
            IndexSpec(("school_id",), name="rag_documents_school_id_idx"),
            IndexSpec(("school_id", "status"), name="rag_documents_school_status_idx"),
            IndexSpec(("knowledge_base_id",), name="rag_documents_knowledge_base_id_idx"),
        ),
    ),
    "rag_chunks": CollectionSchema(
        table_name="rag_chunks",
        columns=(
            _col("_id", "TEXT", primary_key=True, nullable=False),
            _col("doc_id", "TEXT"),
            _col("knowledge_base_id", "TEXT"),
            _col("school_id", "TEXT"),
            _col("admin_id", "TEXT"),
            _col("content", "TEXT"),
            _json_col("metadata"),
            _col("created_at", "TIMESTAMPTZ"),
            _col("updated_at", "TIMESTAMPTZ"),
        ),
        indexes=(
            IndexSpec(("doc_id",), name="rag_chunks_doc_id_idx"),
            IndexSpec(("school_id",), name="rag_chunks_school_id_idx"),
            IndexSpec(("knowledge_base_id",), name="rag_chunks_knowledge_base_id_idx"),
        ),
    ),
    "rag_knowledge_bases": CollectionSchema(
        table_name="rag_knowledge_bases",
        columns=(
            _col("_id", "TEXT", primary_key=True, nullable=False),
            _col("name", "TEXT"),
            _col("school_id", "TEXT"),
            _col("admin_id", "TEXT"),
            _col("description", "TEXT"),
            _col("created_at", "TIMESTAMPTZ"),
            _col("updated_at", "TIMESTAMPTZ"),
        ),
        indexes=(
            IndexSpec(("school_id",), name="rag_knowledge_bases_school_id_idx"),
            IndexSpec(("school_id", "name"), unique=True, name="rag_knowledge_bases_school_name_unique"),
        ),
    ),
    "assistants": CollectionSchema(
        table_name="assistants",
        columns=(
            _col("_id", "TEXT", primary_key=True, nullable=False),
            _col("name", "TEXT"),
            _col("school_id", "TEXT"),
            _col("admin_id", "TEXT"),
            _col("knowledge_base_id", "TEXT"),
            _col("is_active", "BOOLEAN", default_sql="TRUE"),
            _col("created_at", "TIMESTAMPTZ"),
            _col("updated_at", "TIMESTAMPTZ"),
        ),
        indexes=(
            IndexSpec(("school_id",), name="assistants_school_id_idx"),
            IndexSpec(("school_id", "name"), unique=True, name="assistants_school_name_unique"),
            IndexSpec(("knowledge_base_id",), name="assistants_knowledge_base_id_idx"),
        ),
    ),
    "system_settings": CollectionSchema(
        table_name="system_settings",
        columns=(
            _col("_id", "TEXT", primary_key=True, nullable=False),
            _col("key", "TEXT"),
            _json_col("value"),
            _col("created_at", "TIMESTAMPTZ"),
            _col("updated_at", "TIMESTAMPTZ"),
            _col("updated_by", "TEXT"),
        ),
    ),
    "system_prompts": CollectionSchema(
        table_name="system_prompts",
        columns=(
            _col("_id", "TEXT", primary_key=True, nullable=False),
            _col("key", "TEXT"),
            _col("locale", "TEXT"),
            _col("school_id", "TEXT"),
            _col("assistant_id", "TEXT"),
            _col("content", "TEXT"),
            _col("version", "INTEGER", default_sql="1"),
            _col("is_active", "BOOLEAN", default_sql="TRUE"),
            _col("updated_at", "TIMESTAMPTZ"),
            _col("updated_by", "TEXT"),
            _col("created_at", "TIMESTAMPTZ"),
        ),
    ),
    "manual_callbacks": CollectionSchema(
        table_name="manual_callbacks",
        columns=(
            _col("_id", "TEXT", primary_key=True, nullable=False),
            _col("conversation_id", "TEXT"),
            _col("parent_id", "TEXT"),
            _col("parent_name", "TEXT"),
            _col("parent_phone", "TEXT"),
            _col("reason", "TEXT"),
            _col("query", "TEXT"),
            _col("resolved", "BOOLEAN", default_sql="FALSE"),
            _col("created_at", "TIMESTAMPTZ"),
            _col("updated_at", "TIMESTAMPTZ"),
        ),
    ),
    "cf_agent_sessions": CollectionSchema(
        table_name="cf_agent_sessions",
        columns=(
            _col("_id", "TEXT", primary_key=True, nullable=False),
            _col("chat_id", "TEXT"),
            _col("conversation_id", "TEXT"),
            _col("parent_id", "TEXT"),
            _col("sender_id", "TEXT"),
            _col("chat_name", "TEXT"),
            _col("chat_type", "INTEGER"),
            _col("chat_status", "INTEGER"),
            _json_col("chat_tag_names"),
            _json_col("last_payload"),
            _col("last_msg_id", "TEXT"),
            _col("created_at", "TIMESTAMPTZ"),
            _col("updated_at", "TIMESTAMPTZ"),
        ),
    ),
}


class InsertOneResult:
    def __init__(self, inserted_id: str) -> None:
        self.inserted_id = inserted_id


class InsertManyResult:
    def __init__(self, inserted_ids: list[str]) -> None:
        self.inserted_ids = inserted_ids


class UpdateResult:
    def __init__(self, matched_count: int, modified_count: int, upserted_id: Optional[str] = None) -> None:
        self.matched_count = matched_count
        self.modified_count = modified_count
        self.upserted_id = upserted_id


class DeleteResult:
    def __init__(self, deleted_count: int) -> None:
        self.deleted_count = deleted_count


class PostgresCompatCursor:
    def __init__(self, collection: "PostgresCompatCollection", query: Optional[dict[str, Any]] = None, projection: Optional[dict[str, Any]] = None) -> None:
        self.collection = collection
        self.query = query
        self.projection = projection
        self._sort: list[tuple[str, int]] = []
        self._skip = 0
        self._limit: Optional[int] = None

    def sort(self, sort_spec: Any, direction: Optional[int] = None) -> "PostgresCompatCursor":
        self._sort = _normalize_sort_spec(sort_spec, direction)
        return self

    def skip(self, count: int) -> "PostgresCompatCursor":
        self._skip = max(0, int(count))
        return self

    def limit(self, count: int) -> "PostgresCompatCursor":
        self._limit = max(0, int(count))
        return self

    async def _load(self) -> list[dict[str, Any]]:
        docs = await self.collection._find_all(self.query)
        if self._sort:
            docs = _sort_documents(docs, self._sort)
        if self._skip:
            docs = docs[self._skip:]
        if self._limit is not None:
            docs = docs[:self._limit]
        return [_apply_projection(doc, self.projection) for doc in docs]

    def __aiter__(self):
        async def _generator():
            for item in await self._load():
                yield item

        return _generator()


class PostgresCompatCollection:
    def __init__(self, pool: asyncpg.Pool, name: str) -> None:
        self.pool = pool
        self.name = name
        self.schema = COLLECTION_SCHEMAS.get(
            name,
            CollectionSchema(
                table_name=name,
                columns=(
                    _col("_id", "TEXT", primary_key=True, nullable=False),
                ),
                extra_column=None,
            ),
        )
        self.table_name = self.schema.table_name

    def _column_specs(self) -> tuple[ColumnSpec, ...]:
        return self.schema.columns

    def _column_names(self) -> list[str]:
        return [column.name for column in self._column_specs()]

    def _known_field_names(self) -> set[str]:
        return {column.name for column in self._column_specs() if column.name != (self.schema.extra_column or "")}

    def _extra_column_name(self) -> str | None:
        return self.schema.extra_column if self.schema.extra_column in self._column_names() else None

    def _row_to_document(self, row: asyncpg.Record) -> dict[str, Any]:
        row_dict = dict(row)
        document: dict[str, Any] = {}
        extra_column = self._extra_column_name()
        for column in self._column_specs():
            if column.name == extra_column:
                continue
            value = row_dict.get(column.name)
            if value is None:
                continue
            if column.codec == "json" and isinstance(value, str):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass
            document[column.name] = value
        if extra_column:
            extra = row_dict.get(extra_column)
            if isinstance(extra, dict):
                document.update(extra)
        return document

    def _prepare_db_value(self, column: ColumnSpec, value: Any) -> Any:
        if value is None:
            return None
        if column.codec == "json":
            return _prepare_jsonb(value)
        if column.db_type == "TIMESTAMPTZ":
            dt = _to_datetime(value)
            return dt or value
        if column.db_type == "BOOLEAN":
            parsed = _to_boolean(value)
            return parsed if parsed is not None else value
        if column.db_type == "INTEGER":
            parsed = _to_integer(value)
            return parsed if parsed is not None else value
        return str(_normalize_scalar(value)) if column.name == "_id" else _normalize_scalar(value)

    async def _ensure_table(self) -> None:
        column_defs: list[str] = []
        for column in self._column_specs():
            parts = [f"{_quote_ident(column.name)} {column.db_type}"]
            if column.primary_key:
                parts.append("PRIMARY KEY")
            if not column.nullable:
                parts.append("NOT NULL")
            if column.default_sql:
                parts.append(f"DEFAULT {column.default_sql}")
            column_defs.append(" ".join(parts))
        sql = f"CREATE TABLE IF NOT EXISTS {_quote_ident(self.table_name)} ({', '.join(column_defs)})"
        async with self.pool.acquire() as conn:
            await conn.execute(sql)
            rows = await conn.fetch(
                """
                SELECT column_name, data_type, udt_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = $1
                """,
                self.table_name,
            )
            existing_columns = {
                row["column_name"]: (row["data_type"], row["udt_name"])
                for row in rows
            }
            expected_columns = {column.name: column for column in self._column_specs()}
            for column in self._column_specs():
                if column.name in existing_columns:
                    continue
                parts = [f"ALTER TABLE {_quote_ident(self.table_name)} ADD COLUMN {_quote_ident(column.name)} {column.db_type}"]
                if column.default_sql:
                    parts.append(f"DEFAULT {column.default_sql}")
                await conn.execute(" ".join(parts))
            for column_name in list(existing_columns.keys()):
                if column_name not in expected_columns:
                    await conn.execute(
                        f"ALTER TABLE {_quote_ident(self.table_name)} DROP COLUMN IF EXISTS {_quote_ident(column_name)}"
                    )
            for column in self._column_specs():
                existing = existing_columns.get(column.name)
                if not existing:
                    continue
                _, udt_name = existing
                current_type = (
                    "TIMESTAMPTZ" if udt_name == "timestamptz"
                    else "TEXT" if udt_name in {"text", "varchar"}
                    else "BOOLEAN" if udt_name == "bool"
                    else "INTEGER" if udt_name in {"int4", "int8"}
                    else "JSONB" if udt_name == "jsonb"
                    else udt_name.upper()
                )
                if current_type == column.db_type:
                    continue
                if column.db_type == "TEXT":
                    await conn.execute(
                        f"ALTER TABLE {_quote_ident(self.table_name)} ALTER COLUMN {_quote_ident(column.name)} TYPE TEXT USING CASE WHEN {_quote_ident(column.name)} IS NULL THEN NULL ELSE {_quote_ident(column.name)}::text END"
                    )
            for index in self.schema.indexes:
                index_name = index.name or f"{self.table_name}_{'_'.join(index.columns)}_{'uniq' if index.unique else 'idx'}"
                unique_sql = "UNIQUE " if index.unique else ""
                cols_sql = ", ".join(_quote_ident(name) for name in index.columns)
                await conn.execute(
                    f"CREATE {unique_sql}INDEX IF NOT EXISTS {_quote_ident(index_name)} ON {_quote_ident(self.table_name)} ({cols_sql})"
                )

    async def _fetch_all_rows(self) -> list[dict[str, Any]]:
        await self._ensure_table()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(f"SELECT * FROM {_quote_ident(self.table_name)}")
        return [self._row_to_document(row) for row in rows]

    async def _write_document(self, document: dict[str, Any]) -> None:
        await self._ensure_table()
        payload = _normalize_document(document)
        doc_id = str(payload["_id"])
        payload["_id"] = doc_id
        extra_column = self._extra_column_name()
        known_fields = self._known_field_names()
        extras = {key: value for key, value in payload.items() if key not in known_fields}
        values: list[Any] = []
        placeholders: list[str] = []
        column_names: list[str] = []
        for idx, column in enumerate(self._column_specs(), start=1):
            column_names.append(_quote_ident(column.name))
            placeholders.append(f"${idx}")
            if column.name == extra_column:
                values.append(self._prepare_db_value(column, extras))
            else:
                values.append(self._prepare_db_value(column, payload.get(column.name)))
        updates = ", ".join(
            f"{_quote_ident(column.name)} = EXCLUDED.{_quote_ident(column.name)}"
            for column in self._column_specs()
            if not column.primary_key
        )
        sql = f"""
        INSERT INTO {_quote_ident(self.table_name)} ({', '.join(column_names)})
        VALUES ({', '.join(placeholders)})
        ON CONFLICT ({_quote_ident('_id')}) DO UPDATE SET {updates}
        """
        async with self.pool.acquire() as conn:
            await conn.execute(sql, *values)

    async def _delete_ids(self, ids: list[str]) -> int:
        if not ids:
            return 0
        await self._ensure_table()
        sql = f"DELETE FROM {_quote_ident(self.table_name)} WHERE {_quote_ident('_id')} = ANY($1::text[])"
        async with self.pool.acquire() as conn:
            result = await conn.execute(sql, ids)
        return int(result.split()[-1])

    async def _find_all(self, query: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
        docs = await self._fetch_all_rows()
        return [doc for doc in docs if _match_query(doc, query)]

    async def create_index(self, fields: Any, unique: bool = False, sparse: bool = False) -> str:
        await self._ensure_table()
        spec = _normalize_sort_spec(fields)
        columns = [field for field, _ in spec if field in self._known_field_names()]
        if not columns:
            return f"{self.table_name}_compat_index"
        index_name = f"{self.table_name}_{'_'.join(columns)}_{'uniq' if unique else 'idx'}"
        cols_sql = ", ".join(_quote_ident(name) for name in columns)
        unique_sql = "UNIQUE " if unique else ""
        async with self.pool.acquire() as conn:
            await conn.execute(
                f"CREATE {unique_sql}INDEX IF NOT EXISTS {_quote_ident(index_name)} ON {_quote_ident(self.table_name)} ({cols_sql})"
            )
        return index_name

    def find(self, query: Optional[dict[str, Any]] = None, projection: Optional[dict[str, Any]] = None) -> PostgresCompatCursor:
        return PostgresCompatCursor(self, query, projection)

    async def find_one(
        self,
        query: Optional[dict[str, Any]] = None,
        projection: Optional[dict[str, Any]] = None,
        sort: Optional[list[tuple[str, int]]] = None,
    ) -> Optional[dict[str, Any]]:
        docs = await self._find_all(query)
        if sort:
            docs = _sort_documents(docs, _normalize_sort_spec(sort))
        if not docs:
            return None
        return _apply_projection(docs[0], projection)

    async def insert_one(self, document: dict[str, Any]) -> InsertOneResult:
        payload = deepcopy(_normalize_document(document))
        payload["_id"] = str(payload.get("_id") or ObjectId())
        await self._write_document(payload)
        return InsertOneResult(payload["_id"])

    async def insert_many(self, documents: list[dict[str, Any]]) -> InsertManyResult:
        inserted_ids: list[str] = []
        for document in documents:
            result = await self.insert_one(document)
            inserted_ids.append(result.inserted_id)
        return InsertManyResult(inserted_ids)

    async def update_one(self, query: dict[str, Any], update: dict[str, Any], upsert: bool = False) -> UpdateResult:
        docs = await self._find_all(query)
        if docs:
            doc = _apply_update(docs[0], update, is_insert=False)
            await self._write_document(doc)
            return UpdateResult(matched_count=1, modified_count=1)
        if not upsert:
            return UpdateResult(matched_count=0, modified_count=0)
        base = _seed_document_from_filter(query)
        base["_id"] = str(base.get("_id") or ObjectId())
        doc = _apply_update(base, update, is_insert=True)
        await self._write_document(doc)
        return UpdateResult(matched_count=0, modified_count=0, upserted_id=str(doc["_id"]))

    async def update_many(self, query: dict[str, Any], update: dict[str, Any], upsert: bool = False) -> UpdateResult:
        docs = await self._find_all(query)
        if not docs and upsert:
            return await self.update_one(query, update, upsert=True)
        modified = 0
        for doc in docs:
            updated = _apply_update(doc, update, is_insert=False)
            await self._write_document(updated)
            modified += 1
        return UpdateResult(matched_count=len(docs), modified_count=modified)

    async def delete_one(self, query: dict[str, Any]) -> DeleteResult:
        docs = await self._find_all(query)
        if not docs:
            return DeleteResult(0)
        deleted = await self._delete_ids([str(docs[0]["_id"])])
        return DeleteResult(deleted)

    async def delete_many(self, query: dict[str, Any]) -> DeleteResult:
        docs = await self._find_all(query)
        ids = [str(doc["_id"]) for doc in docs]
        deleted = await self._delete_ids(ids)
        return DeleteResult(deleted)

    async def count_documents(self, query: Optional[dict[str, Any]] = None) -> int:
        docs = await self._find_all(query)
        return len(docs)

    async def drop(self) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(f"DROP TABLE IF EXISTS {_quote_ident(self.table_name)}")


class PostgresCompatDatabase:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool
        self._collections: dict[str, PostgresCompatCollection] = {}

    def __getitem__(self, name: str) -> PostgresCompatCollection:
        if name not in self._collections:
            self._collections[name] = PostgresCompatCollection(self.pool, name)
        return self._collections[name]

    def __getattr__(self, name: str) -> PostgresCompatCollection:
        return self[name]

    async def command(self, name: str) -> dict[str, Any]:
        if name != "ping":
            raise NotImplementedError(f"Unsupported database command: {name}")
        async with self.pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"ok": 1}


class Database:
    pool: Optional[asyncpg.Pool] = None
    database: Optional[PostgresCompatDatabase] = None


db = Database()


def get_database() -> PostgresCompatDatabase:
    if db.database is None:
        raise RuntimeError("Database not connected")
    return db.database


async def connect_to_postgres() -> None:
    logger.info("连接到 PostgreSQL: %s", settings.POSTGRES_URL)
    target_url = settings.POSTGRES_URL
    try:
        db.pool = await asyncpg.create_pool(
            target_url,
            min_size=1,
            max_size=10,
            ssl=settings.POSTGRES_SSL,
        )
    except asyncpg.InvalidCatalogNameError:
        parsed = urlsplit(target_url)
        db_name = parsed.path.lstrip("/")
        if not db_name:
            raise

        admin_url = urlunsplit(parsed._replace(path="/postgres"))
        logger.warning("PostgreSQL 数据库 %s 不存在，尝试自动创建", db_name)
        admin_conn = await asyncpg.connect(admin_url, ssl=settings.POSTGRES_SSL)
        try:
            exists = await admin_conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1",
                db_name,
            )
            if not exists:
                await admin_conn.execute(f'CREATE DATABASE "{db_name}"')
        finally:
            await admin_conn.close()

        db.pool = await asyncpg.create_pool(
            target_url,
            min_size=1,
            max_size=10,
            ssl=settings.POSTGRES_SSL,
        )
    db.database = PostgresCompatDatabase(db.pool)
    logger.info("PostgreSQL 连接成功")


async def close_postgres_connection() -> None:
    logger.info("关闭 PostgreSQL 连接")
    if db.pool is not None:
        await db.pool.close()
    db.pool = None
    db.database = None


async def init_db_indexes() -> None:
    database = get_database()
    logger.info("📊 初始化 PostgreSQL 表结构...")
    collections = [
        "users",
        "conversations",
        "conversation_profiles",
        "messages",
        "leads",
        "channel_metrics",
        "assistants",
        "rag_knowledge_bases",
        "rag_documents",
        "rag_chunks",
        "system_settings",
        "system_prompts",
        "manual_callbacks",
        "cf_agent_sessions",
    ]
    for collection_name in collections:
        await database[collection_name]._ensure_table()
    logger.info("✅ PostgreSQL 表结构初始化完成")


async def drop_legacy_mongo_tables() -> list[str]:
    """删除早期 Mongo 兼容迁移阶段遗留的 mongo_* 旧表。"""
    if db.pool is None:
        raise RuntimeError("Database not connected")

    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT tablename
            FROM pg_catalog.pg_tables
            WHERE schemaname = 'public' AND tablename LIKE 'mongo\\_%' ESCAPE '\\'
            ORDER BY tablename
            """
        )
        dropped: list[str] = []
        for row in rows:
            table_name = row["tablename"]
            await conn.execute(f"DROP TABLE IF EXISTS {_quote_ident(table_name)} CASCADE")
            dropped.append(table_name)

    if dropped:
        logger.info("✅ 已删除 Mongo 旧表: %s", ", ".join(dropped))
    else:
        logger.info("ℹ️ 未发现 mongo_* 旧表")
    return dropped


async def create_default_teacher():
    database = get_database()
    logger.info("检查是否需要创建默认教师账号...")
    teacher_exists = await database.users.find_one({"role": "teacher"})
    if teacher_exists:
        logger.info("ℹ️  教师账号已存在，跳过创建")
        return

    from .models.user import UserSchema

    default_teacher = UserSchema(
        phone="13800138001",
        password_hash=UserSchema.hash_password("teacher123456"),
        role="teacher",
        name="默认老师",
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    teacher_dict = default_teacher.model_dump(by_alias=True, exclude=["id"])
    await database.users.insert_one(teacher_dict)
    logger.info("✅ 默认教师账号创建成功")


async def ensure_default_admin_accounts():
    database = get_database()
    from .models.user import UserSchema

    defaults = [
        {
            "phone": "admin",
            "password": "admin",
            "role": "school_admin",
            "name": "默认学校管理员",
            "school_id": "default_school",
            "school_name": "默认学校",
            "reset_if_exists": True,
        },
        {
            "phone": "root",
            "password": "root",
            "role": "super_admin",
            "name": "默认超级管理员",
            "school_id": None,
            "school_name": None,
            "reset_if_exists": True,
        },
        {
            "phone": "13800000002",
            "password": "123456",
            "role": "school_admin",
            "name": "默认学校管理员",
            "school_id": "default_school",
            "school_name": "默认学校",
            "reset_if_exists": False,
        },
    ]

    for item in defaults:
        existing = await database.users.find_one({"phone": item["phone"]})
        password_hash = UserSchema.hash_password(item["password"])
        if not existing:
            user = UserSchema(
                phone=item["phone"],
                password_hash=password_hash,
                role=item["role"],  # type: ignore[arg-type]
                name=item["name"],
                school_id=item.get("school_id"),
                school_name=item.get("school_name"),
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            user_dict = user.model_dump(by_alias=True, exclude=["id"])
            await database.users.insert_one(user_dict)
            logger.info("✅ 已创建默认账号 %s / %s (%s)", item["phone"], item["password"], item["role"])
        elif item.get("reset_if_exists", False):
            updates = {
                "role": item["role"],
                "name": item["name"],
                "school_id": item.get("school_id"),
                "school_name": item.get("school_name"),
                "is_active": True,
                "password_hash": password_hash,
                "updated_at": datetime.utcnow(),
            }
            await database.users.update_one({"_id": existing["_id"]}, {"$set": updates})
            logger.info("✅ 重置默认账号 %s / %s (%s)", item["phone"], item["password"], item["role"])
        else:
            logger.info("ℹ️ 账号 %s 已存在，保持原有配置不变", item["phone"])


async def drop_all_collections():
    if not settings.DEBUG:
        raise RuntimeError("⚠️  此操作仅允许在 DEBUG 模式下执行！")
    database = get_database()
    logger.warning("⚠️  正在删除所有集合...")
    collections = ["users", "conversations", "messages", "leads", "conversation_profiles"]
    for collection_name in collections:
        await database[collection_name].drop()
        logger.info("   已删除集合: %s", collection_name)
    logger.info("✅ 所有集合已删除")
