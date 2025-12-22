# DepotButler - AI Coding Agent Instructions

## Architecture Overview

**Clean Architecture** with layered separation:
- **Domain**: `models.py` - Pure Pydantic models (`Edition`, `Subscription`, `UploadResult`)
- **Infrastructure**: `httpx_client.py`, `db/mongodb.py`, `onedrive.py`, `mailer.py`
- **Application**: `workflow.py` (orchestrator), `edition_tracker.py`, `publications.py`
- **Services**: Named as `*Service` or `*Client` classes (e.g., `EmailService`, `HttpxBoersenmedienClient`)

**Key principle**: Parsers/scrapers must NOT perform HTTP requests - use separate client classes.

## Data Flow & MongoDB Integration

MongoDB (`motor` async driver) is central to operations:

1. **Publications** (`publications` collection): All active publications with subscription metadata, delivery preferences, OneDrive folder paths
2. **Recipients** (`recipients` collection): Email/upload recipients with publication-specific preferences
3. **Edition Tracking** (`processed_editions` collection): Deduplication using `{date}_{publication_id}` keys
4. **Config** (`config` collection): Auth cookies, app settings (log level, admin emails)

### Recipient Preferences Architecture

**Current State**:
- All recipients receive "Megatrend Folger"
- Some recipients receive "DER AKTIONÄR E-Paper" (too large for email, OneDrive only)
- Publication-level controls: `email_enabled`, `onedrive_enabled` in `publications` collection
- Recipient-level controls: `publication_preferences` embedded in `recipients` documents

**Planned Features**:
- Per-recipient subscription tracking with paid periods
- Invoicing triggers when subscription `duration_start`/`duration_end` dates change
- Business model: Sell distribution service to recipients as subscriptions

**Workflow** (`workflow.py`):
```
Login → Discover subscriptions → Sync publications to MongoDB →
Loop each active publication → Check if processed → Download PDF →
Email recipients → Upload to OneDrive → Mark processed → Cleanup
```

Publications processed **sequentially** (not parallel) for safety/debugging.

**Discovery & Sync** (`discovery.py`):
- Runs on **every job execution** to detect website changes
- Compares discovered subscriptions with MongoDB state
- Updates metadata if subscription details change (type, duration dates)
- Publications removed from website → marked `active: false` (not deleted)
- Preserves historical data for audit trail

## Development Conventions

### Python Style
- Python 3.13 features preferred
- Type hints everywhere (`def func() -> ReturnType:`)
- Pydantic V2 models for validation
- Async/await with `httpx.AsyncClient` (not requests/Playwright)
- No global state

### Exception Handling
Use domain-specific exceptions from `exceptions.py`:
- `AuthenticationError` - Cookie expired, OAuth failed (user action needed)
- `TransientError` - Network timeout, 5xx errors (retry safe)
- `ConfigurationError` - Missing env vars, invalid config
- `EditionNotFoundError`, `DownloadError`, `UploadError`, `EmailDeliveryError`, etc.

**Never** use bare `except:` - always catch specific exceptions.

## Testing

### Running Tests
```powershell
# Unit tests only (default, mocks external deps)
uv run pytest

# With coverage
uv run pytest --cov=src/depotbutler --cov-report=term

# Integration tests (requires MongoDB on localhost:27017)
uv run pytest -m integration -v
```

### Test Structure
- `conftest.py` - Shared fixtures, sets test env vars BEFORE imports
- `test_*.py` - Unit tests (run by default)
- `test_*_integration.py` - Integration tests (marked `@pytest.mark.integration`, skipped by default)
- Use `pytest-asyncio` for async tests: `@pytest.mark.asyncio`
- Mock external deps: `unittest.mock.AsyncMock` for async functions

### Dry-Run Mode
Test workflows without side effects:
```powershell
python scripts/test_dry_run.py           # Or:
python -m depotbutler --dry-run          # Downloads PDFs but no emails/uploads
```

## Real-World Constraints

**Email Size Limits**: DER AKTIONÄR E-Paper exceeds typical SMTP attachment limits (~25MB)
- Solution: OneDrive-only delivery for large files
- Validates why publication/recipient-level delivery preferences are critical

**Publication Lifecycle**: Subscriptions have finite durations tracked in MongoDB
- `duration_start`, `duration_end` fields for each publication
- Publications marked `active: false` when removed from website (not deleted)
- Enables future invoicing based on subscription period changes

## Key Scripts & Workflows

All scripts assume `$env:PYTHONPATH="src"` (PowerShell) or `PYTHONPATH=src` (bash).

### Initial Setup
```powershell
# 1. OneDrive OAuth (interactive browser flow)
python scripts/setup_onedrive_auth.py

# 2. Initialize app config in MongoDB
uv run python scripts/init_app_config.py

# 3. Discover & seed publications
uv run python scripts/seed_publications.py
```

### Maintenance Scripts
- `update_cookie_mongodb.py` - Refresh auth cookie (3-day cycle)
- `check_recipients.py` - List recipients and preferences
- `test_recipient_filtering.py` - Test recipient logic (no side effects)
- `add_recipient_preferences.py` - Add publication preferences for recipients

### Running the App
```powershell
python -m depotbutler              # Production
python -m depotbutler --dry-run    # Test mode
```

## Settings & Configuration

`settings.py` uses Pydantic Settings with env prefixes:
- `BOERSENMEDIEN_*` - Login credentials
- `ONEDRIVE_*` - OAuth client ID/secret/refresh token
- `SMTP_*` - Email settings
- `DB_*` - MongoDB connection
- `TRACKING_*` - Edition tracking config (retention_days, enabled)
- `DISCOVERY_*` - Publication discovery settings

**Secrets**: Use `.env` locally, environment variables on Azure Container Apps.

## OneDrive Integration

- Simple upload for files <4MB
- **Chunked upload** for files ≥4MB (10MB chunks, 120s timeout per chunk)
- Filename format: `{date}_{Title-Cased-Title}_{issue}.pdf`
- Folder structure: `{base_folder}/{year}/` (if `organize_by_year=True`)

## Code Quality Tools

```powershell
# Linting (Ruff)
uv run ruff check src/ tests/

# Type checking (mypy) - excludes tests/
uv run mypy src/

# Formatting
uv run ruff format src/ tests/
```

**Config**: `pyproject.toml` defines all tool settings.

## Anti-Patterns to Avoid

❌ Performing HTTP requests inside parser/scraper functions
❌ Using `requests` library (use `httpx.AsyncClient`)
❌ Bare `except:` clauses
❌ Missing type hints
❌ Hardcoding publication configs (use MongoDB)
❌ Sequential processing where parallelization is safe (but publications stay sequential)

## Deployment

Azure Container Apps with scheduled jobs:
- See `docs/DEPLOYMENT.md` for full guide
- Script: `scripts/deploy-to-azure.ps1`
- Docker image ~200MB (no browser deps)
- Environment variables in Azure for secrets
