"""Dustess 调试能力配置适配。"""
from __future__ import annotations

from app.core.config import settings


def get_settings():
    """复用后端统一配置实例。"""
    return settings
