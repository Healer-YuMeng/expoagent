import json
import time
from datetime import datetime
from typing import Any, Dict, Optional

import redis.asyncio as aioredis

from app.core.config import settings
from app.db import get_database

PROMPT_COLLECTION = "system_prompts"


class PromptService:
    """
    提示词配置服务
    - 优先走内存缓存（TTL 默认 3 小时）
    - 未命中时读取 PostgreSQL
    - 没有配置则回落到默认模板
    """

    def __init__(self, ttl_seconds: int = 10800):
        self._ttl = ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._defaults: Dict[str, str] = {}
        self._redis = None
        if settings.RAG_REDIS_URL:
            try:
                self._redis = aioredis.from_url(settings.RAG_REDIS_URL, decode_responses=True)
            except Exception:
                self._redis = None

    # -------- 内部缓存 --------
    def _make_cache_key(
        self,
        key: str,
        locale: Optional[str],
        school_id: Optional[str],
        assistant_id: Optional[str],
    ) -> str:
        return f"{key}:{locale or 'default'}:{school_id or 'global'}:{assistant_id or 'default'}"

    def _get_cached(
        self,
        key: str,
        locale: Optional[str],
        school_id: Optional[str],
        assistant_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        cache_key = self._make_cache_key(key, locale, school_id, assistant_id)
        item = self._cache.get(cache_key)
        if not item:
            return None
        if item["expires_at"] < time.time():
            self._cache.pop(cache_key, None)
            return None
        return item

    def _set_cached(
        self,
        key: str,
        locale: Optional[str],
        school_id: Optional[str],
        assistant_id: Optional[str],
        payload: Dict[str, Any],
    ) -> None:
        cache_key = self._make_cache_key(key, locale, school_id, assistant_id)
        self._cache[cache_key] = {
            **payload,
            "expires_at": time.time() + self._ttl,
        }

    async def _get_cached_redis(
        self,
        key: str,
        locale: Optional[str],
        school_id: Optional[str],
        assistant_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        if not self._redis:
            return None
        cache_key = self._make_cache_key(key, locale, school_id, assistant_id)
        try:
            data = await self._redis.get(cache_key)
            if not data:
                return None
            return json.loads(data)
        except Exception:
            # 遇到连接错误则禁用 redis，避免连续报错
            self._redis = None
            return None

    async def _set_cached_redis(
        self,
        key: str,
        locale: Optional[str],
        school_id: Optional[str],
        assistant_id: Optional[str],
        payload: Dict[str, Any],
    ) -> None:
        if not self._redis:
            return
        cache_key = self._make_cache_key(key, locale, school_id, assistant_id)
        try:
            # datetime 等不可序列化字段转字符串
            serializable = json.loads(json.dumps(payload, default=str))
            await self._redis.set(cache_key, json.dumps(serializable), ex=self._ttl)
        except Exception:
            self._redis = None
            return

    # -------- 默认值管理 --------
    def register_default(self, key: str, content: str) -> None:
        self._defaults[key] = content

    def get_default(self, key: str, fallback: Optional[str] = None) -> str:
        if fallback is not None:
            return fallback
        return self._defaults.get(key, "")

    # -------- 核心方法 --------
    async def get_prompt_with_meta(
        self,
        key: str,
        *,
        locale: Optional[str] = None,
        school_id: Optional[str] = None,
        assistant_id: Optional[str] = None,
        default: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        读取提示词，返回内容与元数据：
        {
            "content": "...",
            "is_default": bool,
            "meta": {version, updated_at, updated_by, locale, key}
        }
        """
        cached = self._get_cached(key, locale, school_id, assistant_id)
        if cached:
            return cached

        cached_redis = await self._get_cached_redis(key, locale, school_id, assistant_id)
        if cached_redis:
            # 回填内存缓存，减少 Redis 次数
            self._set_cached(key, locale, school_id, assistant_id, cached_redis)
            return cached_redis

        doc = None
        try:
            db = get_database()
            candidate_queries: list[dict[str, Any]] = []
            if assistant_id:
                if locale:
                    candidate_queries.append({"key": key, "is_active": True, "assistant_id": assistant_id, "locale": locale})
                candidate_queries.append({"key": key, "is_active": True, "assistant_id": assistant_id, "locale": None})
            if school_id:
                if locale:
                    candidate_queries.append({"key": key, "is_active": True, "assistant_id": None, "school_id": school_id, "locale": locale})
                candidate_queries.append({"key": key, "is_active": True, "assistant_id": None, "school_id": school_id, "locale": None})
            if locale:
                candidate_queries.append({"key": key, "is_active": True, "assistant_id": None, "school_id": None, "locale": locale})
            candidate_queries.append({"key": key, "is_active": True, "assistant_id": None, "school_id": None, "locale": None})
            for query in candidate_queries:
                doc = await db[PROMPT_COLLECTION].find_one(query, sort=[("version", -1), ("updated_at", -1)])
                if doc:
                    break
        except Exception as exc:  # pragma: no cover
            # PostgreSQL 不可用时直接回退默认
            logger = getattr(__import__("logging"), "getLogger")(__name__)
            logger.warning("读取提示词时 PostgreSQL 不可用，使用默认值: %s", exc)
            doc = None

        default_value = self.get_default(key, default)
        content = (doc or {}).get("content")
        is_default = False
        if not content:
            content = default_value
            is_default = True

        meta = None
        if doc:
            meta = {
                "key": key,
                "locale": doc.get("locale"),
                "school_id": doc.get("school_id"),
                "assistant_id": doc.get("assistant_id"),
                "version": doc.get("version"),
                "updated_at": doc.get("updated_at"),
                "updated_by": doc.get("updated_by"),
                "is_active": doc.get("is_active", False),
            }

        payload = {
            "content": content,
            "is_default": is_default,
            "meta": meta,
            "default_content": default_value,
        }
        self._set_cached(key, locale, school_id, assistant_id, payload)
        await self._set_cached_redis(key, locale, school_id, assistant_id, payload)
        return payload

    async def get_prompt(
        self,
        key: str,
        *,
        locale: Optional[str] = None,
        school_id: Optional[str] = None,
        assistant_id: Optional[str] = None,
        default: Optional[str] = None,
    ) -> str:
        result = await self.get_prompt_with_meta(
            key,
            locale=locale,
            school_id=school_id,
            assistant_id=assistant_id,
            default=default,
        )
        return result.get("content", "")

    async def set_prompt(
        self,
        key: str,
        content: str,
        *,
        locale: Optional[str] = None,
        school_id: Optional[str] = None,
        assistant_id: Optional[str] = None,
        updated_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        新建版本并设为生效，旧版本 is_active=False
        """
        db = get_database()
        now = datetime.utcnow()

        latest = await db[PROMPT_COLLECTION].find_one(
            {"key": key, "locale": locale, "school_id": school_id, "assistant_id": assistant_id},
            sort=[("version", -1)],
        )
        next_version = (latest.get("version") if latest else 0) or 0
        next_version += 1

        # 关闭旧版本
        await db[PROMPT_COLLECTION].update_many(
            {"key": key, "locale": locale, "school_id": school_id, "assistant_id": assistant_id},
            {"$set": {"is_active": False}},
        )

        doc = {
            "key": key,
            "locale": locale,
            "school_id": school_id,
            "assistant_id": assistant_id,
            "content": content,
            "version": next_version,
            "is_active": True,
            "updated_at": now,
            "updated_by": updated_by,
        }
        await db[PROMPT_COLLECTION].insert_one(doc)

        # 更新缓存
        cache_payload = {"content": content, "is_default": False, "meta": doc}
        self._set_cached(key, locale, school_id, assistant_id, cache_payload)
        await self._set_cached_redis(key, locale, school_id, assistant_id, cache_payload)
        return doc

    async def clear_cache(
        self,
        key: Optional[str] = None,
        locale: Optional[str] = None,
        school_id: Optional[str] = None,
        assistant_id: Optional[str] = None,
    ) -> None:
        if key is None:
            self._cache.clear()
            return
        cache_key = self._make_cache_key(key, locale, school_id, assistant_id)
        self._cache.pop(cache_key, None)
        if self._redis:
            try:
                await self._redis.delete(cache_key)
            except Exception:
                pass


prompt_service = PromptService(ttl_seconds=getattr(settings, "PROMPT_CACHE_TTL", 10800))


def get_prompt_service() -> PromptService:
    return prompt_service


def register_default_prompt(key: str, content: str) -> None:
    prompt_service.register_default(key, content)
