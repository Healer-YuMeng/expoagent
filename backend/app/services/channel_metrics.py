"""渠道统计服务"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.db import PostgresCompatDatabase


CHANNEL_CONFIG = {
    "xhs": "小红书",
    "dy": "抖音",
    "blbl": "哔哩哔哩",
    "wb": "微博",
    "gzh": "微信公众号",
    "wxsp": "微信视频号",
}


def normalize_channel_source(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    candidate = raw.strip().lower()
    # 兼容常见别名
    alias_map = {
        "xiaohongshu": "xhs",
        "little_red_book": "xhs",
        "douyin": "dy",
        "tiktok": "dy",
        "bilibili": "blbl",
        "bili": "blbl",
        "weibo": "wb",
        "gongzhonghao": "gzh",
        "mp": "gzh",
        "wechat_official_account": "gzh",
        "wechat_video": "wxsp",
        "shipinhao": "wxsp",
    }
    if candidate in CHANNEL_CONFIG:
        return candidate
    return alias_map.get(candidate)


async def record_channel_event(
    db: PostgresCompatDatabase,
    channel: str,
    event: str,
) -> None:
    if channel not in CHANNEL_CONFIG:
        return
    if event not in {"visit", "appointment"}:
        return

    now = datetime.utcnow()
    date_keys = {
        "daily": now.strftime("%Y-%m-%d"),
        "monthly": now.strftime("%Y-%m"),
        "yearly": now.strftime("%Y"),
    }
    inc_field = "visit_count" if event == "visit" else "appointment_count"
    for period, date_key in date_keys.items():
        set_on_insert = {"created_at": now}
        if event == "visit":
            set_on_insert["appointment_count"] = 0
        else:
            set_on_insert["visit_count"] = 0
        await db.channel_metrics.update_one(
            {
                "channel": channel,
                "period": period,
                "date_key": date_key,
            },
            {
                "$inc": {inc_field: 1},
                "$set": {"updated_at": now},
                "$setOnInsert": set_on_insert,
            },
            upsert=True,
        )


async def get_channel_stats(
    db: PostgresCompatDatabase,
    period: str,
    date_key: str,
) -> dict[str, dict[str, int]]:
    cursor = db.channel_metrics.find({
        "period": period,
        "date_key": date_key,
    })
    mapping: dict[str, dict[str, int]] = {
        slug: {"visits": 0, "appointments": 0}
        for slug in CHANNEL_CONFIG.keys()
    }
    async for doc in cursor:
        slug = doc.get("channel")
        if slug not in mapping:
            continue
        mapping[slug] = {
            "visits": doc.get("visit_count", 0),
            "appointments": doc.get("appointment_count", 0),
        }
    return mapping


async def ensure_channel_metrics_indexes(db: PostgresCompatDatabase) -> None:
    await db.channel_metrics.create_index([
        ("channel", 1),
        ("period", 1),
        ("date_key", 1),
    ], unique=True)
