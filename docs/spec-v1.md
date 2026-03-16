# The 3rd Space – System Specification (v1.0)

## 1. Overview

"The 3rd Space" is a LINE Official Account-based mediation system for a married couple.

The system acts as a structured third-party counselor bot.

Core principles:
- All user input is submitted via LIFF (not chat text).
- Chat history should contain only:
  - Confirmed understanding summaries
  - Final proposals
- Raw submissions and internal evaluation are not visible to the wife.
- The system uses a 2-phase confirmation model before sending proposals.

---

## 2. Roles

Two roles exist:

- `husband`
- `wife`

Roles are determined by passphrase during LIFF registration:

- "ゆう" → husband
- "まこ" → wife

User identification is based on LINE `userId`.

Re-registration replaces stored `userId` for that role.

---

## 3. High-Level Flow

Each normal submission creates a "turn".

Turn lifecycle:

1. NORMAL submission (18h restricted)
2. Understanding inference generated
3. User confirms:
   - ✅ "理解は正しい"
   - ❌ "理解が間違っている"
4. If ❌ → correction loop (no 18h restriction)
5. If ✅ → 
   - Confirmed understanding sent to both users
   - Proposal generated and sent to both users
   - Turn closed
   - 18h cooldown starts

---

## 4. Rate Limiting Rules

Each user has:

- `lastNormalSubmitAt`
- `activeTurnId`

### Normal Submission Allowed If:

- `lastNormalSubmitAt` is null
OR
- Current time - `lastNormalSubmitAt` >= 18 hours

### Correction Submission Allowed If:

- `activeTurnId` exists
- Turn status is OPEN

Correction submissions do NOT reset cooldown timer.

Cooldown starts only after:
- Understanding confirmed (✅)
- Proposal sent
- Turn closed

---

## 5. Data Model (Minimal Normalized Design)

### settings
| key | value |
|-----|-------|
| husbandPassphrase |
| wifePassphrase |
| husbandUserId |
| wifeUserId |

---

### users
| userId | role | activeTurnId | lastNormalSubmitAt |

Notes:
- `cooldownUntil` is derived (not stored)
- UI display fields may be calculated in spreadsheet

---

### turns
| turnId | role | status | needsCorrection | understandingText | proposalText |

status values:
- OPEN
- CONFIRMED
- CLOSED

needsCorrection:
- true after ❌ pressed
- false after new understanding generated

---

### submissions
| submittedAt | turnId | role | type | payloadJson |

type:
- NORMAL
- CORRECTION

---

### processed_ids
| id | type | processedAt |

Used for idempotency (postback/message deduplication).

---

## 6. Event Handling

### A. Register (LIFF)
- Validate passphrase
- Map role
- Store userId in settings
- Insert/Update users table

---

### B. Normal Submission (LIFF)
- Validate cooldown
- Generate turnId (YYYYMMDDHHmmssSSS)
- Insert into turns (status=OPEN)
- Set users.activeTurnId
- Store submission (NORMAL)
- Generate understandingText
- Send understanding to submitting user only (with ✅/❌ buttons)

---

### C. Postback ❌
- Validate turnId matches activeTurnId
- Set turns.needsCorrection = true
- Notify submitting user to submit correction via LIFF

---

### D. Correction Submission (LIFF)
- Validate activeTurnId exists
- Store submission (CORRECTION)
- Generate new understandingText
- Send to submitting user only

---

### E. Postback ✅
- Validate turnId matches activeTurnId
- turns.status = CONFIRMED
- Send confirmed understanding to BOTH users
- Generate proposal
- Send proposal to BOTH users
- Write proposal to shared sheet
- turns.status = CLOSED
- users.activeTurnId = null
- users.lastNormalSubmitAt = now()

---

## 7. Message Visibility Rules

Understanding inference:
- Sent ONLY to submitting user
- Shared with both users ONLY after confirmation

Proposal:
- Always sent to BOTH users
- Also stored in shared sheet

Raw submissions:
- Never sent to chat
- Stored only internally

---

## 8. Turn ID Format

Format:
YYYYMMDDHHmmssSSS

Example:
20260228231105987

Must be unique per turn.

---

## 9. Architectural Constraints

- LIFF handles:
  - userId retrieval
  - UI state
  - JSON validation
  - API calls to backend

- GAS handles:
  - State management
  - LINE message sending
  - Proposal generation
  - Rate limiting validation

- Spreadsheet handles:
  - Display calculations (remaining time, etc.)
  - Human-readable proposal storage

---

## 10. Design Philosophy

- Minimize stored state.
- Derive values instead of storing redundant fields.
- Keep state machine explicit.
- Avoid exposing intermediate inference.
- Prevent conversational escalation via staged confirmation.
- Enforce fairness via symmetric role handling.

---

End of Specification v1.0