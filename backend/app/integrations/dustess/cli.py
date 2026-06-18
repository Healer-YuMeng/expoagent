from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

import typer
from rich import print
from rich.pretty import Pretty
from rich.table import Table

from .client import CFAgentClient, DustessCallbackVerifier
from .config import get_settings

app = typer.Typer(add_completion=False, help="尘锋 Dustess API 测试 CLI")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@app.command("show-config")
def show_config():
    cfg = get_settings()
    data = {
        "CF_AGENT_BASE_URL": cfg.CF_AGENT_BASE_URL,
        "CF_AGENT_CLIENT_ID": cfg.CF_AGENT_CLIENT_ID,
        "CF_AGENT_CALLBACK_TOKEN": cfg.CF_AGENT_CALLBACK_TOKEN,
        "CF_AGENT_ENCODING_AES_KEY": cfg.CF_AGENT_ENCODING_AES_KEY,
        "CF_AGENT_RECEIVE_ID": cfg.CF_AGENT_RECEIVE_ID,
        "CF_AGENT_SCRM_ACCOUNT_ID": cfg.CF_AGENT_SCRM_ACCOUNT_ID,
        "CF_AGENT_USER_ID": cfg.CF_AGENT_USER_ID,
        "CF_AGENT_TEST_CHAT_ID": cfg.CF_AGENT_TEST_CHAT_ID,
        "CF_AGENT_TEST_QW_USER_ID": cfg.CF_AGENT_TEST_QW_USER_ID,
        "CF_AGENT_TEST_TARGET_IDS": cfg.CF_AGENT_TEST_TARGET_IDS,
    }
    table = Table("Key", "Value")
    for key, value in data.items():
        table.add_row(key, json.dumps(value, ensure_ascii=False))
    print(table)


@app.command("token")
def fetch_token(force: bool = typer.Option(False, "--force", "-f", help="强制刷新 token")):
    client = CFAgentClient()

    async def runner():
        return await client.get_access_token(force_refresh=force)

    token = asyncio.run(runner())
    print(f"[green]accessToken[/green]: {token}")


@app.command("send-msg")
def send_msg(
    chat_id: Optional[str] = typer.Option(None, "--chat-id", help="会话 chatID"),
    text: str = typer.Option(..., "--text", "-t", help="要发送的文本内容"),
):
    client = CFAgentClient()
    settings = get_settings()
    chat_id = chat_id or settings.CF_AGENT_TEST_CHAT_ID
    if not chat_id:
        raise typer.BadParameter("缺少 chatID，请通过 --chat-id 指定或在 .env 设置 CF_AGENT_TEST_CHAT_ID")

    async def runner():
        return await client.send_agent_message(chat_id=chat_id, msg_type=0, contents=[text])

    data = asyncio.run(runner())
    print(Pretty(data))


@app.command("direct-send")
def direct_send(
    target_ids: Optional[str] = typer.Option(None, "--targets", help="逗号分隔的 targetId 列表"),
    message: str = typer.Option(..., "--text", "-t", help="文本消息内容"),
    target_type: str = typer.Option("single", "--type", "-y", help="目标类型 single/group"),
):
    client = CFAgentClient()
    settings = get_settings()
    targets = target_ids.split(",") if target_ids else settings.CF_AGENT_TEST_TARGET_IDS
    if not targets:
        raise typer.BadParameter("缺少 targetIds，请通过 --targets 指定或在 .env 配置 CF_AGENT_TEST_TARGET_IDS")

    async def runner():
        messages = [{"msgType": 0, "content": message}]
        return await client.direct_send(messages, target_type=target_type, target_ids=targets)

    data = asyncio.run(runner())
    print(Pretty(data))


@app.command("proxy")
def proxy(
    path: str = typer.Argument(..., help="API 路径，例如 /ai/v1/agent/msg/sendMsg"),
    method: str = typer.Option("GET", "--method", "-X"),
    params: Optional[str] = typer.Option(None, "--params", help="JSON 字符串形式的查询参数"),
    payload: Optional[str] = typer.Option(None, "--data", "-d", help="JSON 字符串请求体"),
):
    client = CFAgentClient()

    async def runner():
        query = json.loads(params) if params else {}
        body = json.loads(payload) if payload else {}
        return await client.forward_proxy(method.upper(), path, params=query, json_data=body)

    data = asyncio.run(runner())
    print(Pretty(data))


@app.command("decrypt")
def decrypt_callback(
    msg_signature: str = typer.Option(..., "--signature"),
    timestamp: str = typer.Option(..., "--timestamp"),
    nonce: str = typer.Option(..., "--nonce"),
    echo_str: str = typer.Option(..., "--echo"),
):
    verifier = DustessCallbackVerifier()
    payload = verifier.decrypt_message(
        msg_signature=msg_signature,
        timestamp=timestamp,
        nonce=nonce,
        encrypted=echo_str,
    )
    print(Pretty(payload))


def main():
    app()


if __name__ == "__main__":
    main()
