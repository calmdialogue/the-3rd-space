# The 3rd Space – API Specification (v1.0)

This document defines the API contract between:
- LIFF frontend ⇄ Backend (GAS Web App)
- LINE Messaging API ⇄ Backend (GAS Webhook)

Design goals:
- Minimal surface area (few endpoints, explicit actions)
- Deterministic state machine behavior
- Idempotent handling of LINE webhook/postbacks
- LIFF never sends chat messages; only calls backend

---

## 0. Base URLs

### 0.1 GAS Web App (LIFF API)
- Base: `https://script.google.com/macros/s/<DEPLOYMENT_ID>/exec`
- Method: `POST` (JSON)
- Content-Type: `application/json; charset=utf-8`

### 0.2 GAS Webhook (LINE callback)
- Same GAS project can host webhook `doPost(e)` as well.
- LINE will `POST` to the configured webhook URL.

> Implementation note:
> GAS has only `doPost(e)` entrypoint. Distinguish callers by payload:
> - LIFF API calls include `action` field
> - LINE webhook payload includes `events` array

---

## 1. Authentication / Trust Model

### 1.1 LIFF API
- No user passwords; identity is `userId` from `liff.getProfile()`.
- The backend MUST treat `userId` as untrusted input (client can spoof).
- Therefore, any security-sensitive actions must be validated server-side:
  - `REGISTER` requires correct passphrase
  - `SUBMIT_*` requires `userId` to be already registered (or passphrase-derived role)
  - Rate-limits enforced on server

### 1.2 LINE Webhook
- Verify LINE signature header `X-Line-Signature` (recommended).
- Idempotency required (LINE may retry).

---

## 2. Common Types

### 2.1 Role
- `role`: `"husband" | "wife"`

### 2.2 Turn
- `turnId`: string, format `YYYYMMDDHHmmssSSS`
- `status`: `"OPEN" | "CONFIRMED" | "CLOSED"`

### 2.3 Submission Type
- `"NORMAL" | "CORRECTION"`

### 2.4 Error Response (standard)
All LIFF API errors should return JSON:
```json
{
  "ok": false,
  "error": {
    "code": "SOME_CODE",
    "message": "Human-readable message (JP recommended)",
    "details": { "any": "optional" }
  }
}

Success response:

{ "ok": true, "data": { } }


⸻

3. LIFF ⇄ GAS API

3.1 STATUS

Purpose:
	•	Determine registration state, role, active turn presence, and rate-limit display inputs.

Request:

{
  "action": "status",
  "userId": "Uxxxxxxxx"
}

Response (registered):

{
  "ok": true,
  "data": {
    "registered": true,
    "role": "husband",
    "activeTurnId": "20260228231105987",
    "lastNormalSubmitAt": "2026-02-28T14:11:05.987Z"
  }
}

Response (unregistered):

{
  "ok": true,
  "data": {
    "registered": false,
    "role": null,
    "activeTurnId": null,
    "lastNormalSubmitAt": null
  }
}

Notes:
	•	Backend returns raw timestamps only.
	•	Remaining time text can be computed by Spreadsheet or LIFF UI.
	•	Backend may also optionally include display fields if read from sheet “view columns”, but should not compute them itself (project rule).

Errors:
	•	none (prefer returning registered=false)

⸻

3.2 REGISTER

Purpose:
	•	Bind userId to husband or wife based on passphrase.
	•	Re-registration overwrites stored userId for that role.

Request:

{
  "action": "register",
  "userId": "Uxxxxxxxx",
  "passphrase": "ゆう"
}

Success:

{
  "ok": true,
  "data": {
    "registered": true,
    "role": "husband"
  }
}

Errors:
	•	BAD_PASSPHRASE
	•	MISSING_USER_ID
	•	MISSING_PASSPHRASE

Optional behavior (v1.0 recommendation):
	•	Re-registration is allowed and overwrites the existing role binding.
	•	If you later want stricter control, add:
	•	REQUIRE_OVERRIDE=true and an override passphrase.

⸻

3.3 SUBMIT_NORMAL

Purpose:
	•	Start a new turn (18h restricted).
	•	Store submission payload.
	•	Generate understanding inference.
	•	Send understanding to submitting user only (with ✅/❌ postback buttons).

Request:

{
  "action": "submitNormal",
  "userId": "Uxxxxxxxx",
  "payloadJson": "{...JSON string...}"
}

Success:

{
  "ok": true,
  "data": {
    "turnId": "20260228231105987",
    "status": "OPEN"
  }
}

Errors:
	•	UNREGISTERED_USER
	•	COOLDOWN_ACTIVE
details should include at least lastNormalSubmitAt and/or remainingSeconds if available from sheet.
	•	ACTIVE_TURN_EXISTS
	•	INVALID_JSON

Side effects (server must perform):
	•	Create turn
	•	Set users.activeTurnId
	•	Append submission log
	•	Call OpenAI to generate understandingText
	•	Push LINE message (understanding + ✅/❌ buttons) to submitting user only

⸻

3.4 SUBMIT_CORRECTION

Purpose:
	•	Submit correction within an existing active OPEN turn (no cooldown).
	•	Regenerate understanding inference.
	•	Send new understanding to submitting user only (with ✅/❌ buttons).

Request:

{
  "action": "submitCorrection",
  "userId": "Uxxxxxxxx",
  "payloadJson": "{...JSON string...}"
}

Success:

{
  "ok": true,
  "data": {
    "turnId": "20260228231105987",
    "status": "OPEN"
  }
}

Errors:
	•	UNREGISTERED_USER
	•	NO_ACTIVE_TURN
	•	TURN_NOT_OPEN
	•	INVALID_JSON

Side effects:
	•	Append submission log (CORRECTION)
	•	Update turns.understandingText
	•	Push LINE message to submitting user only (understanding + ✅/❌ buttons)

⸻

4. LINE Webhook ⇄ GAS (Inbound)

LINE sends:
	•	Message events (optional; not used for inputs in this design)
	•	Postback events (used for ✅/❌)

We only rely on postback events.

4.1 POSTBACK Payload Contract (what we send in buttons)

When sending understanding to user, include two postback actions:
	•	OK button:
	•	data: action=ok&turnId=<turnId>
	•	WRONG button:
	•	data: action=wrong&turnId=<turnId>

Example postback data string:
	•	"action=ok&turnId=20260228231105987"
	•	"action=wrong&turnId=20260228231105987"

Backend must parse:
	•	action
	•	turnId

⸻

5. Postback Processing (Server-side)

5.1 POSTBACK WRONG (❌)

Trigger:
	•	LINE webhook event type postback
	•	data contains action=wrong

Validation (must):
	•	sender userId is registered
	•	turnId == users.activeTurnId for sender
	•	turn.status == OPEN

Behavior:
	•	set turn.needsCorrection = true
	•	reply to sender with instruction:
	•	“訂正提出モードです。LIFFから補足を提出してください（18時間制限なし）”
	•	include LIFF deep link if available

No message to the other user.

Idempotency:
	•	If same postback event is repeated:
	•	Do nothing if already processed (dedupe by webhook event id if available)
	•	Or if needsCorrection already true, sending the same instruction is acceptable but not ideal.

Errors / Rejections:
	•	Stale button: turnId != activeTurnId → ignore or send “無効です”
	•	Turn not OPEN → ignore

⸻

5.2 POSTBACK OK (✅)

Trigger:
	•	data contains action=ok

Validation (must):
	•	sender registered
	•	turnId == users.activeTurnId
	•	turn.status == OPEN

Behavior (ordered, must be atomic-ish):
	1.	Set turn.status = CONFIRMED
	2.	Send confirmed understanding (turn.understandingText) to BOTH users (Step 2.5)
	3.	Generate proposal based on confirmed understanding + submission context
	4.	Send proposal to BOTH users (Step 3)
	5.	Append proposal to shared sheet
	6.	Set turn.status = CLOSED
	7.	Clear users.activeTurnId
	8.	Update users.lastNormalSubmitAt = now() (start cooldown)

Idempotency:
	•	Must prevent sending duplicates if webhook retries:
	•	If turn.status == CLOSED, treat as already done and no-op.
	•	If turn.status == CONFIRMED but not CLOSED, resume from last completed step if tracked; for v1.0, simplest is:
	•	If CONFIRMED and proposal already stored in turn.proposalText or shared sheet row exists, skip regeneration and just ensure final sends.
	•	At minimum: CLOSED must be an idempotency boundary.

Errors / Rejections:
	•	Stale button or non-OPEN → ignore or notify invalid.

⸻

6. Outbound Messaging (Server → LINE)

6.1 Understanding Message (private)

Recipient:
	•	Submitting user only

Content:
	•	Latest understanding inference text
	•	Two buttons (postback ok / wrong) with embedded turnId

6.2 Confirmed Understanding Message (shared)

Recipient:
	•	Both husband and wife

Content:
	•	“確定した理解” as a short message
	•	Include the confirmed understandingText

6.3 Proposal Message (shared)

Recipient:
	•	Both husband and wife

Content format (v1.0):
	•	Summary
	•	Background
	•	Options A/B
	•	Questions to each

Also:
	•	Write proposal to shared sheet (proposalText, turnId, timestamp)

⸻

7. Spreadsheet Interaction Contract (Conceptual)

7.1 Internal Sheet Writes (must)
	•	settings: role bindings
	•	users: activeTurnId, lastNormalSubmitAt
	•	turns: status, needsCorrection, understandingText, proposalText
	•	submissions: payloadJson and metadata

7.2 Shared Sheet Writes (must)
	•	proposals: append a row per CLOSED turn
	•	timestamp, turnId, proposalText, status

7.3 Derived Display Fields (optional)
	•	Any “remaining time” / “canSubmit” fields should be computed via sheet formulas,
not in GAS logic, if possible.
	•	Backend may read those fields to return to LIFF UI.

⸻

8. Error Codes (Recommended Set)
	•	UNREGISTERED_USER
	•	BAD_PASSPHRASE
	•	MISSING_USER_ID
	•	MISSING_PASSPHRASE
	•	INVALID_JSON
	•	COOLDOWN_ACTIVE
	•	ACTIVE_TURN_EXISTS
	•	NO_ACTIVE_TURN
	•	TURN_NOT_OPEN
	•	STALE_ACTION (postback turnId mismatch)
	•	INTERNAL_ERROR

⸻

9. Minimal Endpoint Summary

Because GAS uses a single doPost(e):
	•	LIFF API multiplexed by action:
	•	status
	•	register
	•	submitNormal
	•	submitCorrection

LINE webhook:
	•	Detected by presence of events[] and processed accordingly.

End of API spec v1.0

