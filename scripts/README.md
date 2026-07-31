# DepotButler Scripts

**Clean operational scripts** - 12 essential tools for managing the system.

---

## 🚀 Core Operational Scripts

### Setup & Configuration

- **`init_app_config.py`** - Initialize MongoDB app configuration (run once)
- **`setup_onedrive_auth.py`** - Set up OneDrive OAuth (interactive, run once)
- **`seed_publications.py`** - Discover and sync publications from website to MongoDB

### Authentication

- **`update_cookie_mongodb.py`** - Refresh authentication cookie (run every 3 days)

### Data Import & Sync

- **`import_from_onedrive.py`** - **PRIMARY**: Import PDFs from OneDrive archive to MongoDB (correct dates)
- **`sync_web_urls.py`** - **SUPPLEMENTAL**: Sync download URLs from website to MongoDB entries

### Recipients Management

- **`check_recipients.py`** - List all recipients and their preferences
- **`add_recipient_preferences.py`** - Add/modify recipient publication preferences

### Azure Job Operations

- **`list-job-executions.ps1`** - List all DepotButler Azure job executions with pagination-safe newest-first sorting
	- Optional: fetch latest execution logs in one command (`-ShowLatestLogs`)
	- Fail-fast by default for logs lookup (`-ReplicaSearchDepth 1`), increase only if needed
	- Live tail right after a job start: `-ShowLatestLogs -Follow`

### OneDrive Management

- **`set_custom_onedrive_folder.py`** - Configure custom OneDrive folder for publication

---

## 🔧 Maintenance & Troubleshooting

- **`check_mongodb_status.py`** - Check MongoDB connection and database health
- **`inspect_edition.py`** - Inspect specific edition details (debugging)
- **`reset_archive.py`** - ⚠️ **DANGEROUS** - Clear MongoDB collections (start fresh)

---

## 🗂️ Archive

Obsolete scripts have been moved to `scripts/archive/obsolete/` (52 scripts):

- Analysis/debug scripts (duplicates, verification, investigation)
- Blob storage scripts (not using Azure Blob Storage)
- One-off fixes and migrations
- Legacy import attempts

These are preserved for reference but not actively maintained.

---

## 📋 Typical Workflows

### Initial Setup (Once)

```powershell
# 1. Setup OneDrive OAuth
uv run python scripts/setup_onedrive_auth.py

# 2. Initialize app config
uv run python scripts/init_app_config.py

# 3. Discover publications
uv run python scripts/seed_publications.py
```

### Regular Maintenance (Automated via Azure Container Apps)

```powershell
# Update auth cookie (every 3 days)
uv run python scripts/update_cookie_mongodb.py

# Run main workflow (daily)
python -m depotbutler

# Show latest Azure job executions
./scripts/list-job-executions.ps1

# Show latest execution logs (tail 100 lines)
./scripts/list-job-executions.ps1 -ShowLatestLogs -Tail 100

# Stream logs for a fresh run (recommended immediately after triggering a job)
./scripts/list-job-executions.ps1 -ShowLatestLogs -Follow

# Expand replica search if latest execution replica metadata is already gone
./scripts/list-job-executions.ps1 -ShowLatestLogs -ReplicaSearchDepth 3
```

### One-Time Data Import (Recommended Workflow)

```powershell
# Step 1: PRIMARY - Import historical PDFs from OneDrive (correct dates)
uv run python scripts/import_from_onedrive.py

# Step 2: SUPPLEMENTAL - Enrich with download URLs from website
uv run python scripts/sync_web_urls.py
```

---

## 🔧 Maintenance & Troubleshooting

- **`check_mongodb_status.py`** - Check MongoDB connection and database health
- **`inspect_edition.py`** - Inspect specific edition details (debugging)
- **`reset_archive.py`** - ⚠️ **DANGEROUS** - Clear MongoDB collections (start fresh)

---

## 🗂️ Archive

Obsolete scripts have been moved to `scripts/archive/obsolete/` (53 scripts):

- Analysis/debug scripts (duplicates, verification, investigation)
- One-off fixes and migrations
- Legacy import attempts (`collect_historical_pdfs.py` - website dates unreliable)

These are preserved for reference but not actively maintained.

---

## 📝 Development Notes

**Before making changes:**

- Read `.github/copilot-instructions.md` for architecture patterns
- Follow clean architecture: Domain → Infrastructure → Application
- Keep parsers/scrapers separate from HTTP clients
- Use domain-specific exceptions from `exceptions.py`

**Testing:**

- Unit tests: `uv run pytest`
- Dry-run mode available on most scripts: `--dry-run`
- Check logs in `data/tmp/` for debugging
