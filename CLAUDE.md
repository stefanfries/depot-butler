# Depot Butler

Automated workflow to download Börsenmedien subscription PDFs, upload to OneDrive, and email to recipients.
Runs on a schedule in Azure Container Apps. Async-first, no browser automation — httpx + cookies only.

## How to run

```bash
uv sync
cp .env.example .env                    # Fill in credentials
python setup_onedrive_auth.py           # One-time interactive OAuth setup for OneDrive
python scripts/test_dry_run.py          # Dry-run: no emails sent, no uploads
python -m depotbutler                   # Full workflow
python -m depotbutler --dry-run         # Test without side effects
```

## Architecture

- `src/depotbutler/main.py` — entry point; parses `--dry-run` flag
- `src/depotbutler/workflow.py` — `DepotButlerWorkflow` orchestrator (main logic)
- `src/depotbutler/httpx_client.py` — Börsenmedien HTTP client (cookie-based auth)
- `src/depotbutler/onedrive.py` — OneDrive upload (chunked for >4MB files)
- `src/depotbutler/mailer/` — email composition and SMTP sending
- `src/depotbutler/db/repositories/` — MongoDB repos: config, publications, editions, recipients
- `src/depotbutler/services/` — business logic: cookie check, notifications, publication processing

### Workflow steps

1. Check if edition already processed → skip if yes (idempotent)
2. Login to Börsenmedien via httpx + cookies
3. Download PDF
4. Email filtered recipients
5. Upload to OneDrive (10MB chunks for large files)
6. Notify admin with consolidated status
7. Mark edition as processed
8. Clean up temp files

## Key behaviours

- **Cookies expire every ~3 days** and must be manually refreshed — this is the main operational pain point
- Dynamic config (log level, cookie warning threshold, admin emails) is stored in MongoDB and read at runtime — no redeployment needed for config changes
- Dry-run mode must produce zero side effects: no emails, no uploads, no DB writes to processed state
- Chunked upload is 28x faster for large PDFs — don't revert to simple upload

## Infrastructure

- **MongoDB Atlas** — publications, editions, config, recipients collections
- **OneDrive** — OAuth refresh token (set up once via `setup_onedrive_auth.py`)
- **SMTP** — GMX or compatible
- **Azure Container Apps** — scheduled container execution
- **Azure Blob Storage** — optional long-term archival (Cool tier)

## Testing

```bash
uv run pytest tests/ -v    # 35 test files, >85% coverage
```
