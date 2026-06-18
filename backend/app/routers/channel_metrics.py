"""渠道统计回调"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.db import get_database
from app.services.channel_metrics import record_channel_event, normalize_channel_source, CHANNEL_CONFIG

router = APIRouter(prefix="/api/v1/channel-metrics", tags=["渠道统计"])


class ChannelEventRequest(BaseModel):
    source: str = Field(..., description="渠道缩写，例如 xhs/dy/blbl")


@router.post("/visit", summary="记录渠道访问")
async def track_channel_visit(payload: ChannelEventRequest, db=Depends(get_database)):
    channel = normalize_channel_source(payload.source)
    if not channel:
        raise HTTPException(status_code=400, detail="未知的渠道缩写")
    await record_channel_event(db, channel, "visit")
    return {"message": "recorded", "channel": channel}


@router.get("/channels", summary="获取支持的渠道列表")
async def list_channels():
    return {"channels": CHANNEL_CONFIG}
