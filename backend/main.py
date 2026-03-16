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
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger("t3s_webhook")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://calmdialogue.github.io",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

def get_user_row_by_user_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Read users sheet and return the matching row for a LINE userId."""
    spreadsheet_id = _get_env("GSHEET_SPREADSHEET_ID")
    sheet_name = os.getenv("GSHEET_USERS_SHEET_NAME", "users")

    service = _build_sheets_service()
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"{sheet_name}!A:E",
    ).execute()

    values = result.get("values", [])
    if not values:
        return None

    header = values[0]
    rows = values[1:] if len(values) > 1 else []
    header_index = {column: idx for idx, column in enumerate(header)}
    user_id_idx = header_index.get("userId")
    if user_id_idx is None:
        return None

    fields = ["spaceId", "userId", "role", "activeTurnId", "lastNormalSubmitAt"]
    field_indices = {field: header_index.get(field) for field in fields}

    def get_cell(row: List[str], index: Optional[int]) -> str:
        return row[index] if index is not None and 0 <= index < len(row) else ""

    for row in rows:
        row_user_id = get_cell(row, field_indices["userId"])
        if row_user_id == user_id:
            return {
                field: get_cell(row, field_indices[field]) for field in fields
            }

    return None

def append_user_row(user_id: str, role: str) -> None:
    spreadsheet_id = _get_env("GSHEET_SPREADSHEET_ID")
    sheet_name = os.getenv("GSHEET_USERS_SHEET_NAME", "users")

    service = _build_sheets_service()

    values = [
        "",  # spaceId
        user_id,
        role,
        "",  # activeTurnId
        "",  # lastNormalSubmitAt
    ]

    body = {"values": [values]}

    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"{sheet_name}!A:E",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body=body,
    ).execute()

def append_liff_submission(user_id: str, role: str, text: str) -> None:
    spreadsheet_id = _get_env("GSHEET_SPREADSHEET_ID")
    sheet_name = os.getenv("GSHEET_SHEET_NAME", "events")

    service = _build_sheets_service()

    ts = datetime.now(timezone.utc).isoformat()

    values = [
        ts,                # ts
        user_id,           # sourceId
        "liff_submit",     # eventType
        "text",            # messageType
        text,              # messageText
        json.dumps(
            {
                "source": "liff",
                "userId": user_id,
                "role": role,
                "text": text,
            },
            ensure_ascii=False,
        ),                 # rawJson
    ]

    body = {"values": [values]}

    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"{sheet_name}!A:F",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body=body,
    ).execute()

@app.get("/")
def health_get():
    return PlainTextResponse("OK", status_code=200)

@app.post("/liff/status")
async def liff_status(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)

    user_id = payload.get("userId")
    if not isinstance(user_id, str) or not user_id.strip():
        return JSONResponse({"ok": False, "error": "missing_user_id"}, status_code=400)

    try:
        row = await run_in_threadpool(get_user_row_by_user_id, user_id.strip())
    except Exception as e:
        logger.exception("LIFF status lookup failed: %s", e)
        return JSONResponse({"ok": False, "error": "status_lookup_failed"}, status_code=500)

    if not row:
        return JSONResponse({
            "ok": True,
            "registered": False,
        })

    return JSONResponse({
        "ok": True,
        "registered": True,
        "role": row["role"],
        "activeTurnId": row["activeTurnId"],
        "lastNormalSubmitAt": row["lastNormalSubmitAt"],
    })

@app.post("/liff/register")
async def liff_register(request: Request):

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)

    user_id = payload.get("userId")
    passphrase = payload.get("passphrase")

    if not isinstance(user_id, str) or not user_id.strip():
        return JSONResponse({"ok": False, "error": "missing_user_id"}, status_code=400)

    if not isinstance(passphrase, str) or not passphrase.strip():
        return JSONResponse({"ok": False, "error": "missing_passphrase"}, status_code=400)

    user_id = user_id.strip()
    passphrase = passphrase.strip()

    # すでに登録済みか確認
    try:
        row = await run_in_threadpool(get_user_row_by_user_id, user_id)
    except Exception as e:
        logger.exception("User lookup failed: %s", e)
        return JSONResponse({"ok": False}, status_code=500)

    if row:
        return JSONResponse({
            "ok": True,
            "role": row["role"]
        })

    # 合言葉判定
    role = None

    if passphrase == "ゆう":
        role = "husband"

    elif passphrase == "まこ":
        role = "wife"

    if not role:
        return JSONResponse({"ok": False, "error": "invalid_passphrase"}, status_code=400)

    # usersシートに登録
    try:
        await run_in_threadpool(append_user_row, user_id, role)
    except Exception as e:
        logger.exception("User register failed: %s", e)
        return JSONResponse({"ok": False}, status_code=500)

    return JSONResponse({
        "ok": True,
        "role": role
    })

@app.post("/liff/submit")
async def liff_submit(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)

    user_id = payload.get("userId")
    text = payload.get("text")

    if not isinstance(user_id, str) or not user_id.strip():
        return JSONResponse({"ok": False, "error": "missing_user_id"}, status_code=400)

    if not isinstance(text, str) or not text.strip():
        return JSONResponse({"ok": False, "error": "missing_text"}, status_code=400)

    user_id = user_id.strip()
    text = text.strip()

    # 登録済みユーザー確認
    try:
        row = await run_in_threadpool(get_user_row_by_user_id, user_id)
    except Exception as e:
        logger.exception("User lookup failed in submit: %s", e)
        return JSONResponse({"ok": False, "error": "user_lookup_failed"}, status_code=500)

    if not row:
        return JSONResponse({"ok": False, "error": "user_not_registered"}, status_code=400)

    role = row["role"]

    # events シートへ保存
    try:
        await run_in_threadpool(append_liff_submission, user_id, role, text)
    except Exception as e:
        logger.exception("LIFF submission append failed: %s", e)
        return JSONResponse({"ok": False, "error": "submission_append_failed"}, status_code=500)

    return JSONResponse({
        "ok": True,
        "role": role,
    })

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
