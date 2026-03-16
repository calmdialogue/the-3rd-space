いい流れ。
これは「今は実装しないが、将来迷わないための設計凍結文書」だね。

v2実装前提の叩き台として、
そのまま docs/agreement-feature-v2.md に置ける形でまとめる。

⸻


# Agreement Feature – v2 Implementation Draft

Status: Draft (Not implemented in v1)  
Scope: Shared agreement recording with evidentiary integrity

---

## 1. Purpose

The Agreement feature formalizes mutually accepted rules derived from proposals.

It serves two roles:

1. Shared structured memory between husband and wife
2. Potential evidentiary record in case of legal dispute

This feature is intentionally separated from v1 to ensure:
- Core mediation loop stability first
- Legal-sensitive logic designed carefully

---

## 2. High-Level Concept

Agreements are:

- Derived from confirmed proposals (sourceTurnId required)
- Explicitly recorded
- Immutable (append-only)
- Version-controlled (revision tracked, not overwritten)
- Hashed for tamper detection

---

## 3. Data Model (Shared Sheet: `agreements`)

Schema:

agreementId	version	agreedAt	sourceTurnId	title	content	status	supersedesAgreementId	hash

### Column Definitions

- agreementId  
  Format: `A-<sourceTurnId>-<seq2>`  
  Example: `A-20260301120000123-01`

- version  
  Integer, starts at 1

- agreedAt  
  ISO8601 UTC timestamp (server time)

- sourceTurnId  
  Reference to originating proposal

- title  
  Short descriptive label

- content  
  Explicit agreement text (no ambiguity, conditional branches required)

- status  
  ACTIVE / REVISED / VOID

- supersedesAgreementId  
  Previous agreement replaced by this one (if revision)

- hash  
  SHA256(agreementId + "|" + agreedAt + "|" + content)

---

## 4. Agreement Creation Flow (A-Mode / LIFF Trigger)

### Trigger
LIFF action: `createAgreement`

### Required Inputs
- userId
- sourceTurnId
- title
- content

### Server Processing Steps (GAS)

1. Acquire ScriptLock
2. Validate sourceTurnId exists
3. Determine next sequence number for that sourceTurnId
4. Generate agreementId
5. Set agreedAt = server timestamp
6. Generate SHA256 hash
7. Append row to agreements sheet
8. Release lock
9. Send agreement notification to both parties via LINE

---

## 5. LINE Notification Template

Both parties receive identical message:

【Agreement Recorded】

Agreement ID: A-20260301120000123-01
Agreed At: 2026-03-01T12:34:56Z
Source Proposal: 20260301120000123

Title: 家計負担割合
Content:


Hash: 

Purpose:
- Dual-channel trace (Spreadsheet + LINE)
- Tamper detection anchor
- Timestamp confirmation

---

## 6. Evidence Strengthening (Optional Enhancements)

### Level 1 (Free, Recommended)
- Both parties respond in LINE with:
  - "同意します"
- Conversation retained in LINE history

### Level 2
- Monthly PDF export of agreements sheet
- Stored in Google Drive with version history

### Level 3 (Paid / External)
- Cloud-based electronic signature service
- Formal digital signature

---

## 7. Immutability Policy

- Agreements are append-only
- No row updates allowed
- Revisions create new row
- Previous row marked REVISED
- supersedesAgreementId populated

---

## 8. Security Considerations

- Only server may generate agreementId
- Client cannot supply agreementId
- Hash must be server-generated
- All timestamps use server time
- ScriptLock required to prevent race conditions

---

## 9. Known Limitations (v2 Draft)

- Does not enforce dual confirmation automatically
- Relies on user discipline for explicit LINE confirmation
- Spreadsheet itself is mutable (mitigated by hash + history)

---

## 10. Migration Path (Future FastAPI)

This feature can migrate cleanly to:

- agreements table in relational DB
- hash verification endpoint
- PDF archival automation
- Optional blockchain timestamp anchoring

---

End of Agreement Feature Draft
