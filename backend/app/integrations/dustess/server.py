from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from .client import CFAgentClient, DustessCallbackVerifier

logger = logging.getLogger(__name__)

app = FastAPI(title="Dustess Callback Tester", version="0.1.0")

LOG_FILE = Path(__file__).resolve().parent / "callback.log"


def get_verifier() -> DustessCallbackVerifier:
    try:
        return DustessCallbackVerifier()
    except Exception as exc:  # pragma: no cover
        logger.error("初始化 callback verifier 失败: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/callback")
async def verify_callback(
    request: Request,
    verifier: DustessCallbackVerifier = Depends(get_verifier),
):
    params = request.query_params
    msg_signature = params.get("msg_signature") or params.get("msgSignature")
    timestamp = params.get("timestamp") or params.get("timeStamp")
    nonce = params.get("nonce")
    echo_str = params.get("echo_str")
    if not all([msg_signature, timestamp, nonce, echo_str]):
        raise HTTPException(status_code=400, detail="缺少验签参数")

    try:
        plaintext = verifier.verify_url(
            msg_signature=msg_signature,
            timestamp=timestamp,
            nonce=nonce,
            echo_str=echo_str,
        )
    except Exception as exc:
        logger.warning("解密失败: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    logger.info("URL 验证通过: %s", plaintext)
    return PlainTextResponse(content=plaintext, media_type="text/plain")


@app.post("/callback")
async def callback(
    request: Request,
    verifier: DustessCallbackVerifier = Depends(get_verifier),
    client: CFAgentClient = Depends(CFAgentClient),
):
    del client
    try:
        body = await request.json()
    except Exception:
        body = {}

    payload: Dict[str, Any]
    try:
        if "body" in body and isinstance(body["body"], dict) and "encrypt" in body["body"]:
            body_data = body["body"]
        else:
            body_data = body

        encrypt = body_data.get("encrypt")
        if encrypt:
            payload = verifier.decrypt_message(
                msg_signature=body_data.get("msgSignature") or body.get("msg_signature"),
                timestamp=body_data.get("timeStamp") or body.get("timestamp"),
                nonce=body_data.get("nonce"),
                encrypted=encrypt,
            )
        else:
            payload = body
    except Exception as exc:
        logger.error("回调解密失败: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_text = json.dumps(payload, ensure_ascii=False)
    logger.info("收到回调: %s", log_text)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as fp:
            fp.write(log_text + "\n")
    except Exception as exc:  # pragma: no cover
        logger.warning("写入回调日志失败: %s", exc)

    return JSONResponse({"code": 1, "msg": "ok"})
