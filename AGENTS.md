# AGENTS.md

Guidelines for AI agents working in this repository.

This project is built with **AI-assisted development** (Codex, Copilot, Cursor, etc.).  
Agents must follow these rules to maintain architectural integrity and prevent structural degradation.

The goal is **stable, maintainable implementation**, not rapid patching.

Always produce an implementation plan before writing code.

---

# 1. Files To Read First

Before implementing any feature, read:

1. README.md
2. AGENTS.md

These define the architecture and development rules.

Additional documents should be read **only when relevant**:

| File | When to read |
|-----|-------------|
| ORIGIN.md | When modifying system behavior or dialogue logic |
| docs/state-machine.md | When implementing turn lifecycle or counselor flow |
| docs/data-model.md | When interacting with Google Sheets schema |

See `ORIGIN.md` for the philosophical foundation of the system.

---

# 2. System Architecture

The system consists of four main layers.

LINE Official Account
│
▼
LIFF Frontend
│
▼
Cloud Run Backend (FastAPI)
│
▼
Google Sheets
│
▼
State Machine (Google Apps Script)

Responsibilities are strictly separated.

| Layer | Responsibility |
|------|---------------|
| LINE | Message transport |
| LIFF | User structured input |
| Backend | API + persistence |
| Sheets | Data storage |
| GAS | Dialogue state machine |

Agents **must not move responsibilities between layers**.

Example:  
Dialogue logic must not be implemented in the backend.

---

# 3. Backend Responsibilities

Location:

/backend

The backend is a **FastAPI service deployed on Google Cloud Run**.

Responsibilities:

- LINE webhook handling
- LIFF API endpoints
- Google Sheets persistence
- User registration
- Submission intake

Current endpoints:

POST /
LINE webhook

POST /liff/status
POST /liff/register
POST /liff/submit

Agents must **not change endpoint contracts** unless explicitly instructed.

---

# 4. Spreadsheet Schema Is Stable

Google Sheets acts as the system database.

Schema definitions exist in:

docs/data-model.md

Agents must **never change**:

- sheet names
- column names
- column order

unless explicitly instructed.

Breaking schema compatibility will break the system.

---

# 5. Dialogue Logic Location

Dialogue logic lives in:

/gas-server

This layer contains the **state machine**.

Responsibilities include:

- turn lifecycle
- understanding inference
- proposal generation
- dialogue control

The backend must remain **stateless except for logging and submission intake**.

Agents must **not implement dialogue logic in the backend**.

---

# 6. Design Invariants

The following rules must not be violated.

1. Understanding must be confirmed before proposals are generated
2. Unconfirmed inference must remain private
3. Only confirmed understanding is shared
4. Raw submissions must never be directly shared
5. One active turn per user
6. Cooldown prevents impulsive exchanges
7. Webhook processing must be idempotent

These rules originate from the system philosophy in ORIGIN.md.

---

# 7. Implementation Planning Rule

Before modifying code, the agent must first produce a short implementation plan.

The plan should include:

1. Files that will be modified
2. New files that will be created (if any)
3. Responsibility of each file
4. High-level flow of the change

Only after presenting this plan should the agent proceed with implementation.

The agent must never start writing code immediately.

This rule exists to prevent unstructured patches and maintain clean architecture.

---

# 8. Code Organization Rules

Agents must prefer **clean architecture over shortest implementation**.

Avoid monolithic files and mixed responsibilities.

## Separation of Concerns

Separate:

- request parsing
- validation
- persistence
- external API calls
- business logic

Routes must remain thin.

---

# 9. Backend File Structure Rules

Prefer splitting by responsibility.

Recommended structure:

backend/

main.py
FastAPI app creation
route wiring

line_api.py
LINE signature verification
reply helpers

sheets.py
Google Sheets read/write helpers

users.py
user lookup
registration logic

submissions.py
LIFF submission handling

models.py
request/response schemas

Rules:

- Do not place multiple responsibilities into one file
- Do not expand `main.py` indefinitely
- Extract reusable logic early

---

# 10. Route Design Rules

API routes must be thin.

Routes should only:

1. parse request
2. call a dedicated function
3. return response

Routes should not contain long business logic blocks.

Example pattern:

@app.post(”/liff/submit”)
async def submit(req: Request):
payload = parse_request(req)
result = await handle_submission(payload)
return result

Business logic must be implemented elsewhere.

---

# 11. Refactoring Rule

If a file exceeds roughly **200–300 lines**, or starts mixing responsibilities:

Refactor before adding more functionality.

Agents should prefer **early modularization**.

---

# 12. Naming Rules

File and function names must reflect responsibilities.

Good:

users.py
sheets.py
line_api.py
submissions.py

Bad:

helpers.py
utils2.py
misc.py

Avoid generic names.

---

# 13. Dependency Rules

Agents must avoid unnecessary dependencies.

Prefer:

- Python standard library
- existing dependencies already used in the repository

Do not introduce new libraries without strong justification.

---

# 14. Commit Message Convention

All commits must follow this format:

: 

Types:

feat     new feature
fix      bug fix
docs     documentation changes
refactor internal restructuring
infra    infrastructure / deployment
style    formatting only

Examples:

feat: implement /liff/submit endpoint
fix: correct LINE signature verification
docs: update architecture description
infra: update Cloud Run deployment config
refactor: extract sheets helpers

Guidelines:

- Use present tense
- Keep subject under ~72 characters
- One logical change per commit

---

# 15. Security Rules

Agents must never:

- expose secrets
- commit API keys
- modify environment variable names
- bypass webhook signature verification
- disable authentication checks

Security rules are strict.

---

# 16. Implementation Strategy

Agents must prioritize:

1. architectural stability
2. maintainability
3. clarity
4. minimal safe changes

Avoid:

- large speculative refactors
- over-engineering
- complex abstractions

---

# 17. When Requirements Are Unclear

If instructions are ambiguous:

1. preserve architecture
2. avoid schema changes
3. implement minimal behavior
4. request clarification

Do not guess architectural changes.

---

# 18. Project Intent

This system is **not a chatbot**.

It is a **structured mediation system** designed to prevent emotional escalation and misunderstanding.

Agents must respect the system's purpose as described in:

ORIGIN.md

The intent of the system must not be compromised by implementation shortcuts.
