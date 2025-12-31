# Scripts Cleanup Plan

## Current State: 62 Scripts (Way Too Many!)

### 🟢 KEEP - Core Operational Scripts (8)
**These are essential for running the system**

1. `init_app_config.py` - Initialize MongoDB config
2. `seed_publications.py` - Discover and sync publications
3. `setup_onedrive_auth.py` - OAuth setup
4. `update_cookie_mongodb.py` - Refresh auth cookie
5. `check_recipients.py` - List recipients
6. `add_recipient_preferences.py` - Manage recipient preferences
7. `collect_historical_pdfs.py` - Download historical editions from web
8. `sync_web_urls.py` - Sync download URLs to MongoDB

### 🟡 KEEP - Maintenance/Admin Scripts (3)
**Useful for troubleshooting but not daily operations**

1. `check_mongodb_status.py` - Database health check
2. `inspect_edition.py` - Inspect specific edition details
3. `reset_archive.py` - Clean slate (dangerous but sometimes needed)

### 🟠 CONSOLIDATE - OneDrive Import (Keep 1, Delete Rest)
**Multiple attempts at OneDrive import - need ONE good version**

KEEP: Create new `import_onedrive_archive.py` (fresh start)
DELETE:
- `import_from_onedrive.py` (old version)
- `reset_and_import_onedrive.py` (wrapper)
- `analyze_onedrive_pdfs.py` (analysis)
- `list_onedrive_folders.py` (analysis)
- `rename_onedrive_pdfs.py` (one-off fix)
- `fix_onedrive_filename_typos.py` (one-off fix)
- `verify_onedrive_filenames.py` (analysis)
- `convert_onedrive_share_url.py` (utility)
- `set_custom_onedrive_folder.py` (one-off config)
- `migrate_onedrive_organize_to_publications.py` (one-off migration)

### 🔴 DELETE - Analysis/Debug Scripts (27)
**One-off analysis scripts that served their purpose**

Duplicates Analysis (13 scripts!):
- `analyze_duplicates.py`
- `analyze_duplicate_pattern.py`
- `analyze_editions.py`
- `analyze_megatrend.py`
- `extract_duplicate_urls.py`
- `final_duplicate_summary.py`
- `find_duplicate_dates.py`
- `identify_duplicate_ausgabe_ids.py`
- `identify_duplicate_dates.py`
- `map_duplicate_dates.py`
- `investigate_date_mismatch.py`
- `fix_duplicate_filenames.py`
- `list_unique_editions.py`

Import Verification (8 scripts):
- `check_import_results.py`
- `check_final_results.py`
- `final_verification.py`
- `verify_archival.py`
- `check_edition_fields.py`
- `check_edition_metadata.py`
- `export_unique_editions_csv.py`
- `update_edition_metadata.py`

Specific Issue Investigation (6 scripts):
- `check_2019_issues.py`
- `check_early_years.py`
- `check_all_mongodb.py`
- `find_missing_issues.py`
- `verify_issue_18.py`
- `check_mongodb_count.py`

### 🔴 DELETE - Blob Storage Scripts (14)
**We're NOT using Azure Blob Storage - these are obsolete**

- `check_blob_state.py`
- `check_blob_storage.py`
- `cleanup_extra_blobs.py`
- `find_extra_blobs.py`
- `fix_blobs.py`
- `investigate_blob_issues.py`
- `test_blob_exists.py`
- `test_blob_service.py`
- `verify_blob_paths.py`
- `migrate_file_paths.py`
- `test_archival_notification.py`
- `test_archival_setup.py`
- `test_enhanced_schema.py`

### 🔴 DELETE - One-Off Fixes (3)
**Temporary fixes that are no longer needed**

- `cleanup_incomplete_editions.py`
- `delete_last_edition.py`
- `force_reprocess_edition.py`
- `fix_publication_id.py`

### 🟢 KEEP - Deployment (1)
- `deploy-to-azure.ps1`

---

## Summary

**Current:** 62 scripts
**Keep:** 12 scripts
**Delete:** 50 scripts (81% reduction!)

---

## Action Plan

### Phase 1: Cleanup (Now)
1. Move all DELETE scripts to `scripts/archive/obsolete/` (don't delete yet, just in case)
2. Keep only the 12 essential scripts in `scripts/`

### Phase 2: Fresh OneDrive Import (Next)
Create new `import_onedrive_archive.py` with better design:

**Proposed Structure:**
```
MongoDB: processed_editions
{
  "edition_key": "2024_04_megatrend-folger",  // YYYY_II_publication-id
  "publication_id": "megatrend-folger",
  "publication_date": "2024-01-25",
  "issue_number": 4,
  "issue_year": 2024,
  "title": "Megatrend Folger 04/2024",
  
  // OneDrive source
  "onedrive_path": "/2024/2024-01-25_Megatrend-Folger_04.pdf",
  "onedrive_file_id": "...",
  "onedrive_imported_at": "2025-12-31T12:00:00Z",
  
  // Web source (added by sync_web_urls.py)
  "download_url": "https://...",
  "web_synced_at": "2025-12-31T12:30:00Z",
  
  // Metadata
  "source": "onedrive",  // or "web" or "both"
  "has_pdf": true,
  "created_at": "2025-12-31T12:00:00Z"
}
```

**Key Improvements:**
1. Parse issue_number and issue_year from filename (not from date)
2. Store OneDrive file_id for future re-downloads
3. Clear separation: OneDrive = archive, Web = download URLs
4. Single source of truth: MongoDB edition_key
5. Idempotent: Can re-run without creating duplicates

### Phase 3: Validation
After import, verify:
- All PDFs in OneDrive have MongoDB entries
- Edition keys match pattern YYYY_II_publication-id
- Issue numbers parsed correctly from filenames
- No duplicates

---

## Questions for You

1. **OneDrive Filename Pattern**: What's the current structure?
   - Example: `2024-01-25_Megatrend-Folger_04.pdf`?
   - Do all files follow same pattern?

2. **Issue Number Source**: Should we parse from:
   - Filename (`_04.pdf`) - RECOMMENDED
   - Or Date (week number) - NOT RELIABLE

3. **Historical Data**: Do we keep the 607 current MongoDB entries?
   - Or start completely fresh?

4. **Web Sync**: Should we run sync_web_urls.py after import?
   - To enrich with download URLs?
