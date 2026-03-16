# The 3rd Space – Data Model (v1.0)

This document defines the minimal, normalized data model stored in Google Spreadsheets.

Goals:
- Minimal columns, explicitly state-driven
- No redundant derived fields stored (derive via formulas or UI)
- Easy to inspect manually
- Supports: registration, turns, submissions, idempotency, shared proposal archive

Spreadsheets:
- `夫婦カウンセリング_管理用` (private, operational DB)
- `夫婦カウンセリング_対話記録` (shared, readable archive for the couple)

---

## 0. Conventions

### 0.1 Time
- Store timestamps as ISO 8601 strings in UTC (recommended), e.g.:
  - `2026-02-28T14:11:05.987Z`
- Alternatively store as spreadsheet DateTime, but be consistent.

### 0.2 IDs
- `userId`: LINE user identifier (string)
- `turnId`: time-based unique id `YYYYMMDDHHmmssSSS` (string)

### 0.3 Normalization Rule
- Do not store values that can be deterministically derived from other stored values.
- Exception: store “indexes” that prevent scanning (e.g., `lastNormalSubmitAt`).

---

## 1. T3S_internal (Private)

### 1.1 Sheet: `settings` (Key/Value)
Purpose:
- Store passphrases and current userId bindings.

Schema:
| key | value |
|---|---|
| husbandPassphrase | ゆう |
| wifePassphrase | まこ |
| husbandUserId | (LINE userId) |
| wifeUserId | (LINE userId) |

Notes:
- Passphrases are stored in plaintext by design (private use only).
- Re-registration overwrites `<role>UserId`.

Optional keys (future):
- `overridePassphrase` (for safer rebind)
- `schemaVersion`

---

### 1.2 Sheet: `users`
Purpose:
- Minimal per-user operational state for cooldown and turn linkage.

Schema:
| userId | role | activeTurnId | lastNormalSubmitAt |
|---|---|---|---|

Definitions:
- `role`: `husband` or `wife`
- `activeTurnId`:
  - null/blank if no active turn
  - set to the currently OPEN turn created by NORMAL submission
- `lastNormalSubmitAt`:
  - timestamp of last completed NORMAL turn (updated when the turn is CLOSED)
  - used for 18-hour cooldown

Normalization notes:
- `cooldownUntil` is derived: `lastNormalSubmitAt + 18 hours`
- “Can submit” is derived from:
  - NORMAL allowed if cooldown passed AND activeTurnId blank
  - CORRECTION allowed if activeTurnId not blank

Optional "view" columns (computed by spreadsheet formulas, not required for backend):
- `cooldownUntil` (computed)
- `remainingText` (computed)
- `canNormalSubmit` (computed)
- `canCorrectionSubmit` (computed)

> Backend must NOT rely solely on these computed columns for enforcement.
> They exist only for UI display convenience.

---

### 1.3 Sheet: `turns`
Purpose:
- Turn-level state machine storage.

Schema:
| turnId | role | status | needsCorrection | understandingText | proposalText | createdAt |
|---|---|---|---|---|---|---|

Required columns:
- `turnId`: string, unique
- `role`: initiating role (`husband`/`wife`)
- `status`: `OPEN` / `CONFIRMED` / `CLOSED`
- `needsCorrection`: boolean (TRUE/FALSE)
- `understandingText`: latest inferred understanding (private until confirmed)
- `proposalText`: final proposal text (shared after confirmed)
- `createdAt`: timestamp (optional if turnId encodes time; still useful for sorting)

Normalization notes:
- `status` is the idempotency boundary:
  - if `CLOSED`, POSTBACK_OK must be a no-op.
- `needsCorrection` is a minimal flag to indicate correction mode.
  - set TRUE on ❌
  - reset FALSE on new understanding generation or after ✅

Operational notes:
- `understandingText` and `proposalText` are stored as “final outputs”, not derived.
- If you later want structure:
  - store `proposalJson` separately, or
  - store `proposalText` as canonical and derive formatted output for chat.

---

### 1.4 Sheet: `submissions`
Purpose:
- Immutable append-only log of all LIFF submissions (raw JSON).

Schema:
| submittedAt | turnId | role | type | payloadJson |
|---|---|---|---|---|

Definitions:
- `type`: `NORMAL` or `CORRECTION`
- `payloadJson`: raw JSON string as submitted

Normalization notes:
- `lastNormalSubmitAt` in `users` is an index to avoid scanning this sheet.

Operational notes:
- This sheet is internal only (not shared with wife).
- Consider adding optional columns later if needed:
  - `parseOk` (boolean)
  - `error` (string)

---

### 1.5 Sheet: `processed_ids`
Purpose:
- Minimal idempotency/deduplication store for LINE webhook retries.

Schema:
| id | type | processedAt |
|---|---|---|

Definitions:
- `id`: webhook event identifier or a stable dedupe key
- `type`: `postback` | `message` | `other`
- `processedAt`: timestamp

Notes:
- Keep only the recent window (e.g., last 7–30 days) if the sheet grows.
- If LINE does not provide a stable id for some events, create a dedupe key using:
  - `userId + turnId + action + timestampBucket` (last resort)

---

## 2. T3S_shared (Shared / Read-only for couple)

### 2.1 Sheet: `proposals`
Purpose:
- Human-readable archive of finalized proposals.

Schema:
| timestamp | turnId | initiatedBy | confirmedUnderstanding | proposalText | status |
|---|---|---|---|---|---|

Minimum required:
- `timestamp` (when proposal finalized)
- `turnId`
- `proposalText`

Recommended:
- `initiatedBy`: `husband`/`wife`
- `confirmedUnderstanding`: the confirmed understanding shared to both users
- `status`: e.g., `FINAL`

Notes:
- This sheet is meant to be the “official record”.
- Keep formatting human-friendly.
- No raw payloadJson or internal evaluation here.

---

## 3. Data Integrity Rules (Enforced by Backend)

### 3.1 Registration integrity
- Only passphrase may bind a `userId` to a role.
- Re-registration overwrites role binding in `settings`.

### 3.2 Turn integrity
- NORMAL submission:
  - creates a new row in `turns` with `status=OPEN`
  - sets `users.activeTurnId`
- CORRECTION submission:
  - must reference existing OPEN `turnId` via `users.activeTurnId`

### 3.3 Visibility integrity
- `submissions.payloadJson` never goes to shared sheets or shared chat outputs.
- Only `confirmedUnderstanding` and `proposalText` become shared outputs.

### 3.4 Cooldown integrity
- Update `users.lastNormalSubmitAt` only after turn becomes `CLOSED`.

### 3.5 Idempotency boundary
- If `turns.status == CLOSED`, POSTBACK_OK must not send messages again.

---

## 4. Suggested Spreadsheet Formulas (Optional UI Support)

These are optional "view columns" for display. Backend must not depend on them.

In `users`:

### cooldownUntil (if lastNormalSubmitAt exists)
- `=IF(D2="", "", D2 + TIME(18,0,0))`

### remainingMinutes
- `=IF(E2="", "", MAX(0, (E2 - NOW())*24*60))`

### canNormalSubmit
- `=AND(activeTurnId="", OR(lastNormalSubmitAt="", NOW()>=cooldownUntil))`

### canCorrectionSubmit
- `=activeTurnId<>""`

### remainingText (example)
- Convert remainingMinutes into "あとX時間Y分"
  (exact formula depends on locale/time format; keep it simple)

---

## 5. Migration Note (Future FastAPI)

This model maps cleanly to relational DB tables:
- settings → key/value table or config table
- users → users table
- turns → turns table
- submissions → submissions log table
- processed_ids → idempotency table
- proposals → shared view/exports

End of data-model v1.0