# TASKS.md

Current implementation status for AI agents.

## Completed

- LINE Messaging API webhook connected
- Cloud Run backend deployed
- Google Sheets logging works
- LIFF frontend is published
- `/liff/status` implemented
- `/liff/register` implemented
- LIFF can open inside LINE

## In Progress

- `/liff/submit` implementation

## Next

1. Implement `/liff/submit`
2. Save LIFF submission into `events` sheet
3. Keep backend logic minimal
4. Do not implement cooldown yet

## Not Yet

- cooldown control
- activeTurnId handling
- OpenAI integration
- GAS state machine integration for proposals
- group delivery logic

## Current constraints

- Do not change spreadsheet schemas
- Do not move state machine logic into backend
- Keep `main.py` thin
- Prefer modularization over inline patches

## Expected test

After `/liff/submit` is implemented:

1. Open LIFF inside LINE
2. Register with passphrase
3. Submit text
4. Confirm one row is appended to `events`
