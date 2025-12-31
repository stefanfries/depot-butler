# DepotButler Scripts

**Clean operational scripts** - 13 essential tools for managing the system.

---

## 🚀 Core Operational Scripts

### Setup & Configuration
- **`init_app_config.py`** - Initialize MongoDB app configuration (run once)
- **`setup_onedrive_auth.py`** - Set up OneDrive OAuth (interactive, run once)
- **`seed_publications.py`** - Discover and sync publications from website to MongoDB

### Authentication
- **`update_cookie_mongodb.py`** - Refresh authentication cookie (run every 3 days)

### Data Import & Sync
- **`import_from_onedrive.py`** - Import PDFs from OneDrive archive to MongoDB
- **`sync_web_urls.py`** - Sync download URLs from website to MongoDB entries
- **`collect_historical_pdfs.py`** - Download historical editions from website

### Recipients Management
- **`check_recipients.py`** - List all recipients and their preferences
- **`add_recipient_preferences.py`** - Add/modify recipient publication preferences

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
```

### One-Time Data Import
```powershell
# Import historical PDFs from OneDrive
uv run python scripts/import_from_onedrive.py

# Enrich with download URLs from website
uv run python scripts/sync_web_urls.py
```

### Historical Collection (Optional)
```powershell
# Download all historical editions from website
uv run python scripts/collect_historical_pdfs.py --start-date 2018-01-01 --end-date 2025-12-31
```

---

## 🎯 Next Steps

Based on the cleanup plan in `docs/SCRIPT_CLEANUP_PLAN.md`:

1. ✅ **Cleanup completed** - Moved 52 obsolete scripts to archive
2. 🔄 **Next: Refactor import_from_onedrive.py** with better architecture:
   - Parse issue numbers from filenames (not dates)
   - Use `YYYY_II_publication-id` as single source of truth
   - Store OneDrive metadata (file_id, path)
   - Make idempotent (can re-run safely)
3. 📊 **Validation** - Verify all imports are correct
4. 🚀 **Production** - Deploy and automate

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
