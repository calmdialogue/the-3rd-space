# The 3rd Space

A state-driven mediation system built on LINE Official Account + LIFF + Google Apps Script.

This project implements a structured third-party counselor for a married couple.
It is not a chatbot — it is a deterministic state machine controlling structured dialogue.

---

## 🎯 Purpose

The system prevents direct argumentative exchanges between husband and wife by enforcing:

1. Structured JSON submissions (via LIFF)
2. Private understanding confirmation
3. Shared proposal output only after confirmation
4. Rate-limited interaction (18-hour cooldown)

The goal is clarity before reaction.

---

## 🧠 Core Design Principles

- No raw arguments in chat.
- Understanding must be confirmed before being shared.
- Only confirmed understanding and final proposals appear in conversation history.
- One active turn per user.
- Minimal, normalized data model.
- Explicit state transitions.

---

## 🏗 Architecture

### Components

- **LINE Official Account**
  - Messaging API
  - Postback handling (✅ / ❌)

- **LIFF (Frontend)**
  - Registration via passphrase
  - JSON submission
  - Status display
  - Cooldown awareness

- **Google Apps Script (Backend)**
  - State machine control
  - Turn lifecycle management
  - Proposal generation
  - LINE message dispatch

- **Google Spreadsheet**
  - Internal state storage  
    - `夫婦カウンセリング_管理用`
  - Shared proposal archive  
    - `夫婦カウンセリング_対話記録`

---

## 🔁 High-Level Flow

1. User submits JSON (NORMAL submission).
2. System generates understanding inference.
3. User confirms:
   - ❌ → correction loop (no cooldown applied)
   - ✅ → confirmed understanding shared
4. Proposal generated and sent to both users.
5. Turn closed.
6. 18-hour cooldown begins.

---

## 🗂 Project Structure

```
the-3rd-space/
├─ liff/                 # Frontend (GitHub Pages target)
├─ gas/                  # Google Apps Script source
├─ docs/
│   ├─ spec-v1.md
│   ├─ state-machine.md
│   ├─ api-spec.md
│   └─ data-model.md
├─ README.md
└─ README-ja.md
```

---

## ⏳ Rate Limiting

- Each user may create one NORMAL submission every 18 hours.
- Correction submissions are allowed within an active turn.
- Cooldown begins only after proposal completion.

---

## 📊 Data Model Overview

Internal spreadsheet:  
**夫婦カウンセリング_管理用**

Core tables:
- settings
- users
- turns
- submissions
- processed_ids

Shared spreadsheet:  
**夫婦カウンセリング_対話記録**

- proposals

See `docs/data-model.md` for full schema.

---

## 🔐 Design Boundaries

- Raw submissions are never shared in chat.
- Intermediate understanding is private until confirmed.
- State transitions must be validated server-side.
- Idempotency required for webhook handling.

---

## 🚀 Development Workflow

1. Edit LIFF in `/liff`
2. Deploy via GitHub Pages
3. Update GAS backend
4. Test inside LINE app

---

For detailed behavior:
- State transitions → `docs/state-machine.md`
- API contract → `docs/api-spec.md`
- Data schema → `docs/data-model.md`

---

Version: v1.0