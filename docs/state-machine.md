# The 3rd Space – State Machine (v1.0)

This document describes the explicit state machine for the mediation flow.

Scope:
- One couple (husband + wife)
- Input via LIFF (JSON)
- Confirmation via LINE postback buttons
- Output to LINE (chat) + archive to shared spreadsheet

---

## 1. Entities

### 1.1 User (per role)
- `role`: `husband` | `wife`
- `userId`: LINE user identifier (mutable via re-registration)
- `activeTurnId`: nullable
- `lastNormalSubmitAt`: nullable (used for 18h cooldown)

### 1.2 Turn (per NORMAL submission)
- `turnId`: unique, time-based (YYYYMMDDHHmmssSSS)
- `role`: who initiated the turn (`husband` or `wife`)
- `status`: `OPEN` | `CONFIRMED` | `CLOSED`
- `needsCorrection`: boolean
- `understandingText`: latest inferred understanding (private until confirmed)
- `proposalText`: final proposal (shared)

---

## 2. Core Invariants (Must Always Hold)

### I1. Single active turn per user
- If `users.activeTurnId` is set, it refers to exactly one `turns.turnId` with `status != CLOSED`.

### I2. Normal submissions create turns
- A NORMAL submission always creates a new turn.
- A CORRECTION submission never creates a new turn.

### I3. Correction submissions require an active OPEN turn
- A CORRECTION submission is valid only if:
  - `users.activeTurnId` exists, and
  - referenced `turn.status == OPEN`

### I4. Visibility rule
- `understandingText` is sent only to the submitting user while the turn is OPEN.
- After confirmation (✅), the final confirmed `understandingText` is sent to both users.
- `proposalText` is always sent to both users and archived.

### I5. Cooldown rule (18h)
- NORMAL submissions are restricted per user by `lastNormalSubmitAt`.
- CORRECTION submissions do not update `lastNormalSubmitAt`.
- Cooldown begins only after successful proposal completion (turn CLOSED).

### I6. Postback validation
- ✅/❌ postbacks must include `turnId`.
- Postback actions are accepted only if `turnId == users.activeTurnId` for the sender.
  - Otherwise reject/ignore (stale button protection).

---

## 3. States

This system has:
- User-level state (derived from `activeTurnId`)
- Turn-level state (`turn.status` + `needsCorrection`)

### 3.1 User-level State (Derived)
| User State | Condition |
|---|---|
| `IDLE` | `activeTurnId` is null |
| `IN_TURN` | `activeTurnId` is not null |

> NOTE: User state is derived; do not store separate `userState` columns.

### 3.2 Turn-level State (Stored)
| Turn State | Meaning |
|---|---|
| `OPEN` | Understanding confirmation in progress (includes correction loop) |
| `CONFIRMED` | ✅ pressed; understanding confirmed; proposal generation in progress |
| `CLOSED` | Proposal sent + archived; turn finished |

Aux flag:
- `needsCorrection`:
  - set true when ❌ pressed
  - set false when a new understanding is generated (or after ✅)

---

## 4. Events

### 4.1 LIFF Events
- `REGISTER(passphrase)`
- `SUBMIT_NORMAL(payloadJson)`
- `SUBMIT_CORRECTION(payloadJson)`
- `STATUS_QUERY()` (read-only)

### 4.2 LINE Postback Events
- `POSTBACK_WRONG(turnId)`  (❌)
- `POSTBACK_OK(turnId)`     (✅)

---

## 5. Transition Diagram (Text)

### 5.1 Normal flow (no correction)
```
User(IDLE)
  └─ SUBMIT_NORMAL → Turn(OPEN) created, user.activeTurnId set
        └─ send understanding (private, with ✅/❌)
             └─ POSTBACK_OK → Turn(CONFIRMED)
                    ├─ send confirmed understanding to both (Step 2.5)
                    ├─ generate + send proposal to both (Step 3)
                    ├─ archive proposal to shared
                    └─ Turn(CLOSED), user.activeTurnId cleared, lastNormalSubmitAt updated
```

### 5.2 Correction loop flow
```
User(IDLE)
  └─ SUBMIT_NORMAL → Turn(OPEN) created, send understanding (private)
        └─ POSTBACK_WRONG → needsCorrection = true, prompt correction via LIFF
              └─ SUBMIT_CORRECTION → update understanding (private), needsCorrection=false
                     ├─ POSTBACK_WRONG → loop again (no limit)
                     └─ POSTBACK_OK → proceed to CONFIRMED → CLOSED (same as normal flow)
```

---

## 6. Transition Rules (Formal)

### Rule R1: REGISTER
Input:
- `userId`, `passphrase`
Output:
- assign `role` based on passphrase
- update `settings.<role>UserId = userId`
- upsert `users(userId, role)` (do not touch lastNormalSubmitAt unless new user row)
No turn changes.

### Rule R2: SUBMIT_NORMAL
Preconditions:
- user is registered (role exists)
- cooldown satisfied:
  - `lastNormalSubmitAt` is null OR `now - lastNormalSubmitAt >= 18h`
- user has no active turn:
  - `users.activeTurnId` is null
Actions:
- create new `turnId`
- insert `turns(turnId, role, status=OPEN, needsCorrection=false)`
- set `users.activeTurnId = turnId`
- log submission (NORMAL)
- generate `understandingText`
- send understanding to submitting user only with buttons containing `turnId`
Postconditions:
- Turn is OPEN
- User is IN_TURN

### Rule R3: POSTBACK_WRONG (❌)
Preconditions:
- sender is registered
- `turnId == users.activeTurnId`
- `turn.status == OPEN`
Actions:
- set `turn.needsCorrection = true`
- send instruction to submitting user: "submit correction via LIFF"
Postconditions:
- Turn remains OPEN

### Rule R4: SUBMIT_CORRECTION
Preconditions:
- sender is registered
- `users.activeTurnId` exists
- referenced `turn.status == OPEN`
Actions:
- log submission (CORRECTION)
- generate new `understandingText`
- set `turn.understandingText = newText`
- set `turn.needsCorrection = false`
- send new understanding to submitting user only with ✅/❌ buttons containing `turnId`
Postconditions:
- Turn remains OPEN

### Rule R5: POSTBACK_OK (✅)
Preconditions:
- sender is registered
- `turnId == users.activeTurnId`
- `turn.status == OPEN`
Actions (must be executed in order):
1) set `turn.status = CONFIRMED`
2) send confirmed understanding (`turn.understandingText`) to BOTH users (Step 2.5)
3) generate proposal (`proposalText`) based on confirmed understanding + payload context
4) send proposal to BOTH users (Step 3)
5) archive proposal to shared sheet
6) set `turn.status = CLOSED`
7) set `users.activeTurnId = null`
8) set `users.lastNormalSubmitAt = now()`  (cooldown starts)
Postconditions:
- Turn is CLOSED
- User returns to IDLE

---

## 7. Error Handling / Rejection Rules

### E1: Unregistered user
- Reject any submit/postback except REGISTER and STATUS_QUERY.

### E2: Cooldown violation on SUBMIT_NORMAL
- Reject and return remaining time information (computed by spreadsheet/UI).

### E3: Active turn exists on SUBMIT_NORMAL
- Reject (prevents multiple parallel turns per user).

### E4: Correction without active turn
- Reject SUBMIT_CORRECTION if `users.activeTurnId` is null.

### E5: Stale postback
- Ignore or reply with "This action is no longer valid" if:
  - `turnId != users.activeTurnId`
  - `turn.status != OPEN`

### E6: Idempotency / duplicate events
- Use `processed_ids` to ignore duplicates for:
  - Postbacks
  - Webhook message events
- On duplicate, do nothing (no side effects).

---

## 8. Notes (Implementation Guidance)

- Spreadsheet columns may include derived display values (e.g., remaining cooldown time).
- Backend must enforce correctness even if UI display is wrong.
- Correction loop has no explicit limit in v1.0.
- Understanding is private until confirmed; only confirmed understanding is shared.

End of state-machine v1.0
```