# The 3rd Space

A structured mediation system built on **LINE Official Account + LIFF + Cloud Run + Google Sheets**.

This project implements a **state-driven third-party counselor** for a married couple.

It is **not a chatbot**.  
It is a **deterministic dialogue control system** that structures conversation to prevent emotional escalation and misunderstanding.

---

# 🎯 Purpose

Direct conversation between partners often escalates before mutual understanding is established.

The 3rd Space introduces a **structured intermediary layer** that enforces:

1. Structured submissions
2. Understanding inference
3. Private confirmation of understanding
4. Proposal generation only after confirmation
5. Rate-limited dialogue

The goal is:

**Clarity before reaction.**

---

# 🧠 Core Design Principles

- No raw arguments in chat
- Understanding must be confirmed before being shared
- Only confirmed understanding and final proposals appear in shared history
- One active turn per user
- Explicit state transitions
- Minimal normalized data model
- Cooldown to prevent impulsive exchanges

---

# 🏗 Architecture

## Components

### LINE Official Account

Handles the communication channel.

Responsibilities:

- Receive webhook events
- Deliver counselor outputs
- Handle confirmation actions (✅ / ❌)

---

### LIFF (Frontend)

User interface for structured input.

Responsibilities:

- User registration via passphrase
- JSON-based structured submission
- Status display
- Cooldown awareness

Location:

/liff

Typically deployed via **GitHub Pages**.

---

### Backend (FastAPI on Cloud Run)

Primary API layer for the system.

Responsibilities:

- Handle LINE Messaging API webhook
- Serve LIFF API endpoints
- Persist event logs to Google Sheets
- Handle user registration
- Accept LIFF submissions

Key endpoints:

POST /
LINE webhook

POST /liff/status
Check registration and user state

POST /liff/register
Register user via passphrase

POST /liff/submit
Submit structured input

Location:

/backend

Deployment:

gcloud run deploy

Cloud Run provides:

- HTTPS endpoint
- auto-scaling
- service account based access to Google APIs

---

### Google Apps Script (State Machine Layer)

Controls dialogue logic and turn lifecycle.

Responsibilities:

- Dialogue state transitions
- Turn lifecycle management
- Understanding inference
- Proposal generation
- LINE message dispatch

Location:

/gas-server

This layer implements the **deterministic counselor logic**.

---

### Google Spreadsheet

Persistent storage for system state.

Internal operational database:

夫婦カウンセリング_管理用

Shared dialogue archive:

夫婦カウンセリング_対話記録

---

# 🔁 High-Level Flow

User (LIFF)
│
│ JSON submission
▼
Cloud Run Backend
│
│ store event
▼
Google Sheets
│
▼
State Machine (GAS)
│
│ inference + proposal
▼
LINE Official Account

Detailed flow:

1. User submits structured JSON via LIFF.
2. Backend records the submission.
3. State machine generates understanding inference.
4. User confirms:
   - ❌ correction loop (no cooldown)
   - ✅ understanding confirmed
5. Proposal generated and shared.
6. Turn closed.
7. Cooldown begins.

---

# ⏳ Rate Limiting

Each user may submit a **NORMAL submission every 18 hours**.

Rules:

- Cooldown begins **after proposal completion**
- Correction submissions are allowed during an active turn
- Only one active turn per user

This prevents impulsive exchanges.

---

# 📊 Data Model Overview

Internal spreadsheet:

夫婦カウンセリング_管理用

Core tables:

settings
users
turns
submissions
events
processed_ids

Shared archive:

夫婦カウンセリング_対話記録

Table:

proposals
agreements

Full schema:

docs/data-model.md

---

# 🗂 Project Structure

the-3rd-space/

├─ backend/            # FastAPI Cloud Run service
│  ├─ main.py
│  ├─ requirements.txt
│  └─ Dockerfile
│
├─ liff/               # LIFF frontend
│  ├─ index.html
│  ├─ app.js
│  └─ style.css
│
├─ gas-server/         # Google Apps Script source
│
├─ docs/
│  ├─ state-machine.md
│  ├─ api-spec.md
│  └─ data-model.md
│
├─ ORIGIN.md           # Foundational philosophy
├─ README.md
└─ README-ja.md

---

# 🔐 Design Boundaries

Certain information is intentionally restricted.

Rules:

- Raw submissions are never shared directly
- Unconfirmed understanding remains private
- Only confirmed understanding is shared
- Proposals are shared with both users
- State transitions must be server-side validated
- Webhook processing must be idempotent

---

# 🚀 Development Workflow

Backend:

cd backend
gcloud run deploy

Frontend:

edit /liff
push to GitHub
deploy via GitHub Pages

State machine:

update /gas-server
deploy to Google Apps Script

Testing:

1. Open LIFF inside LINE
2. Submit structured input
3. Confirm understanding
4. Observe proposal output

---

# 📚 Documentation

Detailed documentation is located in `/docs`.

State transitions:

docs/state-machine.md

API contract:

docs/api-spec.md

Data schema:

docs/data-model.md

---

# 📜 Project Origin

The foundational philosophy and motivation for this system are documented in:

ORIGIN.md

This document explains **why the system exists** and defines the principles that must not be compromised.

---

Version: v1.1