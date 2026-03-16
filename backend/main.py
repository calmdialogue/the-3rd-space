import os
import json
import hmac
import base64
import hashlib
import logging
from typing import Any, Dict, Optional, List
from datetime import datetime, timezone

import google.auth
from googleapiclient.discovery import build
from starlette.concurrency import run_in_threadpool

import httpx
from fastapi import FastAPI, Header, Request
from fastapi.responses import PlainTextResponse, JSONResponse


logger = logging.getLogger("t3s_webhook")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

app = FastAPI()


def _get_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v


def verify_line_signature(body_bytes: bytes, x_line_signature: Optional[str]) -> bool:
    """Verify LINE Messaging API signature.

    LINE sends Base64(HMAC-SHA256(channelSecret, requestBody)).
    """
    if not x_line_signature:
        return False
    channel_secret = _get_env("LINE_CHANNEL_SECRET").encode("utf-8")
    mac = hmac.new(channel_secret, body_bytes, hashlib.sha256).digest()
    expected = base64.b64encode(mac).decode("utf-8")
    # Use constant-time compare
    return hmac.compare_digest(expected, x_line_signature)


async def reply_message(reply_token: str, text: str) -> None:
    access_token = _get_env("LINE_CHANNEL_ACCESS_TOKEN")
    url = "https://api.line.me/v2/bot/message/reply"
    payload = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text}],
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code >= 300:
            logger.error("LINE reply failed: %s %s", resp.status_code, resp.text)


def _build_sheets_service():
    """Build Google Sheets API client using Application Default Credentials (ADC).

    On Cloud Run, ADC uses the service account configured for the service.
    """
    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def append_row_to_sheet(values: List[Any]) -> None:
    """Append one row to the configured spreadsheet/tab."""
    spreadsheet_id = _get_env("GSHEET_SPREADSHEET_ID")
    sheet_name = os.getenv("GSHEET_SHEET_NAME", "events")

    service = _build_sheets_service()
    body = {"values": [values]}
    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"{sheet_name}!A:Z",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body=body,
    ).execute()


@app.get("/")
def health_get():
    return PlainTextResponse("OK", status_code=200)


@app.post("/")
async def line_webhook(
    request: Request,
    x_line_signature: Optional[str] = Header(default=None, alias="X-Line-Signature"),
):
    body = await request.body()

    # Reject non-LINE requests
    try:
        if not verify_line_signature(body, x_line_signature):
            return PlainTextResponse("Unauthorized", status_code=401)
    except RuntimeError as e:
        # Misconfiguration (missing env vars). Fail closed.
        logger.exception("Misconfigured env: %s", e)
        return PlainTextResponse("Server misconfigured", status_code=500)

    try:
        payload: Dict[str, Any] = json.loads(body.decode("utf-8"))
    except Exception:
        logger.warning("Invalid JSON payload")
        return PlainTextResponse("Bad Request", status_code=400)

    events = payload.get("events", []) or []
    if not isinstance(events, list):
        return PlainTextResponse("Bad Request", status_code=400)

    # Fixed reply (v1): reply only to message events with a replyToken.
    for ev in events:
        if not isinstance(ev, dict):
            continue

        # Save to spreadsheet (best-effort)
        try:
            ts = datetime.now(timezone.utc).isoformat()
            source = ev.get("source") or {}
            source_id = ""
            if isinstance(source, dict):
                source_id = (
                    source.get("userId")
                    or source.get("groupId")
                    or source.get("roomId")
                    or ""
                )

            ev_type = ev.get("type") or ""
            msg = ev.get("message") or {}
            msg_type = msg.get("type") if isinstance(msg, dict) else ""
            msg_text = msg.get("text") if isinstance(msg, dict) else ""
            raw = json.dumps(ev, ensure_ascii=False)

            await run_in_threadpool(
                append_row_to_sheet,
                [ts, source_id, ev_type, msg_type, msg_text, raw],
            )
        except Exception as e:
            logger.exception("Spreadsheet append failed: %s", e)

        # Fixed reply (v1): reply only to message events with a replyToken.
        reply_token = ev.get("replyToken")
        if ev_type == "message" and reply_token:
            msg = ev.get("message") or {}
            text = "OK"
            # Optional echo-ish behavior for debugging
            if isinstance(msg, dict) and msg.get("type") == "text":
                incoming = msg.get("text")
                if isinstance(incoming, str) and incoming.strip():
                    text = f"OK: {incoming.strip()}"
            await reply_message(reply_token, text)

    # Always return 200 to LINE if signature verified and JSON parsed
    return JSONResponse({"ok": True})