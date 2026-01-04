# DepotButler Master Implementation Plan

**Last Updated**: January 4, 2026
**Status**: Sprint 9 Complete ✅ (Monitoring & Observability - Minimal Version)

---

## Purpose

This document consolidates all past, current, and future implementation work for DepotButler into a single source of truth. It replaces the previous `copilot-plan.md` and `ROADMAP.md` files.

---

## Quick Navigation

- [✅ Completed Sprints](#completed-sprints-1-7) - Sprint 1-7 (Dec 2025)
- [⏳ Near-Term Work](#near-term-sprints-8-10) - Sprints 8-10 (planned)
- [🔮 Future Vision](#future-vision-phases-1-4) - Long-term features
- [📊 System Status](#system-status-december-29-2025) - Current capabilities

---

## Completed Sprints (1-7)

### Sprint 1: Foundation (Multi-Publication Auto-Discovery) ✅

**Completed**: December 14, 2025
**Duration**: 2 days

**Objectives**:

- Auto-discover publications from boersenmedien.com account
- Sync metadata to MongoDB
- Support multiple active publications

**Deliverables**:

1. ✅ Database schema extensions for publications and recipients
2. ✅ `PublicationDiscoveryService` - Auto-discovery from website
3. ✅ Migration scripts (`migrate_recipient_preferences.py`, `migrate_publications_discovery.py`)
4. ✅ Discovery sync integrated into workflow
5. ✅ MongoDB indexes for efficient querying

**Key Files**:

- `src/depotbutler/services/publication_discovery_service.py` (137 lines)
- `src/depotbutler/db/repositories/publication.py` (62 lines)
- `scripts/migrate_recipient_preferences.py`
- `scripts/migrate_publications_discovery.py`

**Commit**: Multiple commits between Dec 13-14, 2025

---

### Sprint 2: Recipient Preferences ✅

**Completed**: December 14, 2025
**Duration**: 2 days

**Objectives**:

- Per-recipient, per-publication delivery preferences
- Custom OneDrive folder paths
- Recipient-specific organize_by_year settings

**Deliverables**:

1. ✅ `get_recipients_for_publication()` - Filter by publication and method
2. ✅ `get_onedrive_folder_for_recipient()` - Custom folder resolution
3. ✅ `get_organize_by_year_for_recipient()` - Setting resolution
4. ✅ `update_recipient_stats()` - Per-publication tracking
5. ✅ Updated mailer service with publication_id parameter
6. ✅ `upload_for_recipients()` - Multi-recipient OneDrive uploads
7. ✅ Comprehensive test suite (20 tests)

**Key Files**:

- `src/depotbutler/db/repositories/recipient.py` (75 lines)
- `src/depotbutler/mailer/service.py` (148 lines)
- `src/depotbutler/onedrive/service.py` (179 lines)
- `tests/test_recipient_preferences.py` (20 tests)

**Schema**:

```javascript
{
  "email": "user@example.com",
  "publication_preferences": [
    {
      "publication_id": "megatrend-folger",
      "enabled": true,
      "email_enabled": true,
      "upload_enabled": false,
      "custom_onedrive_folder": null,
      "organize_by_year": null,  // null = use publication default
      "send_count": 0,
      "last_sent_at": null
    }
  ]
}
```

**Commit**: Multiple commits between Dec 13-14, 2025

---

### Sprint 3: Multi-Publication Processing ✅

**Completed**: December 14, 2025
**Duration**: 1 day

**Objectives**:

- Process all active publications in single workflow run
- Consolidated success notifications
- Per-publication error isolation

**Deliverables**:

1. ✅ Refactored `workflow.py` with publication loop
2. ✅ `_process_single_publication()` method - Isolated processing
3. ✅ Sequential publication processing with error handling
4. ✅ Consolidated summary notifications
5. ✅ Multi-publication integration tests

**Key Changes**:

- Publications processed sequentially (not parallel for safety)
- Each publication gets independent tracking
- Single summary email after all publications processed
- Errors in one publication don't stop others

**Key Files**:

- `src/depotbutler/workflow.py` (230 lines)
- `tests/test_workflow_multi_publication.py` (4 tests)

**Commits**: `1c7193f`, `c5c20f1`

---

### Sprint 4: Tools & Optimizations ✅

**Completed**: December 14, 2025
**Duration**: 1 day

**Objectives**:

- Performance optimization for large files
- Enhanced filename formatting
- Documentation updates

**Deliverables**:

1. ✅ Chunked upload for files >4MB (28x performance improvement)
2. ✅ 10MB chunk size, 120s timeout per chunk
3. ✅ Title-cased filename format: `{date}_{Title-Cased-Title}_{issue}.pdf`
4. ✅ Dry-run mode with `--dry-run` flag
5. ✅ Updated documentation (ONEDRIVE_SETUP.md, architecture.md)

**Performance**:

- Before: 4.5 minutes for 64MB file
- After: 9 seconds for 64MB file
- **Improvement**: 28x faster

**Key Files**:

- `src/depotbutler/onedrive/service.py` - Chunked upload logic
- `src/depotbutler/utils/helpers.py` - Filename generation
- `docs/ONEDRIVE_SETUP.md` - Updated with chunked upload details
- `docs/DRY_RUN_MODE.md` - Dry-run documentation

**Commits**: `ac3402a`, `04b678c`, `892b5a1`, `a05f3b4`

---

## Completed Sprint 5: Blob Storage Archival ✅

**Status**: ✅ **COMPLETE** (90%)
**Started**: December 27, 2025
**Completed**: December 28, 2025

**Objectives**:

- Long-term PDF archival to Azure Blob Storage (Cool tier)
- Enable historical PDF collection
- Avoid repeated downloads with caching layer

**Progress Summary**:

- ✅ Phase 5.1: Foundation (100%) - Schema, BlobStorageService, settings
- ✅ Phase 5.2: Workflow Integration (100%) - Initialization, timestamp tracking
- ✅ Phase 5.3: Archival & Cache (90%) - Archive method, --use-cache flag, tests
  - ⏳ Deferred: Historical collection script (4-5 hours, separate session)
- ✅ Phase 5.4: Testing & Validation (100%) - **End-to-end tested with real edition**

**Sprint 5 Achievements**:

1. **Azure Blob Storage Integration**: Complete archival pipeline from workflow to Azure Storage (Cool tier)
   - Successfully archived Megatrend Folger 51/2025 (699,641 bytes) in production
   - Non-blocking archival with graceful error handling
2. **Caching Layer**: `--use-cache` flag enables retrieval from blob storage instead of website downloads
3. **Granular Timestamps**: MongoDB tracks `downloaded_at`, `email_sent_at`, `onedrive_uploaded_at`, `archived_at`
   - All timestamps verified working correctly in production workflow
4. **Non-Blocking Archival**: Blob storage failures don't impact email/OneDrive delivery
5. **Graceful Degradation**: Workflow continues if blob storage not configured
6. **Comprehensive Testing**: 271 unit tests (including 8 new blob archival tests)
7. **Bug Fixes**: Removed redundant `discover_subscriptions()` call

**End-to-End Validation**:

- ✅ Real PDF archived: `2025/megatrend-folger/2025-12-18_Megatrend-Folger_51-2025.pdf` (0.67 MB)
- ✅ MongoDB metadata complete: blob_url, blob_path, container, file_size, archived_at
- ✅ All workflow steps executed successfully: download → email → upload → **archive**
- ✅ Test scripts created for future validation

**Deferred Work** (10%):

- Historical PDF collection script (`scripts/collect_historical_pdfs.py`) - 4-5 hours
- Cache hit scenario testing (requires new edition)
- Cost monitoring (requires 30 days operational data)
- Cost monitoring (requires 30 days operational data)

### Phase 5.1: Foundation ✅ COMPLETE

**Completed**: December 27, 2025

**Deliverables**:

1. ✅ Azure Storage account created (`depotbutlerarchive`, Germany West Central)
2. ✅ `BlobStorageService` implementation (345 lines)
   - `archive_edition()` - Upload PDF with metadata
   - `get_cached_edition()` - Retrieve from cache
   - `exists()` - Check if edition archived
   - `list_editions()` - Query by publication/year
   - `archive_from_file()` / `download_to_file()` - File operations
3. ✅ `BlobStorageSettings` in Pydantic settings
4. ✅ Enhanced `ProcessedEdition` schema with 9 new fields:
   - `blob_url`, `blob_path`, `blob_container`, `file_size_bytes`, `archived_at`
   - `downloaded_at`, `email_sent_at`, `onedrive_uploaded_at` (granular timestamps)
5. ✅ `EditionRepository` helper methods:
   - `update_email_sent_timestamp()`
   - `update_onedrive_uploaded_timestamp()`
   - `update_blob_metadata()`
6. ✅ Test coverage (test_blob_service.py, test_enhanced_schema.py)
7. ✅ Linting fixes and test environment configuration

**Key Decisions**:

- Blob path convention: `{year}/{publication_id}/{filename}.pdf`
- Example: `2025/megatrend-folger/2025-12-18_Megatrend-Folger_51-2025.pdf`
- Cool tier for cost optimization (archival access pattern)
- Optional connection_string (auto-disabled in test environment)
- Kept `processed_at` as workflow entry timestamp (not redundant with `downloaded_at`)
- Removed `distributed_at` (can derive from MAX(email_sent_at, onedrive_uploaded_at))

**Commits**: `cf843c9`, `1dab547`, `376faca`, `0bf7c7d`

---

### Phase 5.2: Workflow Integration ✅ COMPLETE

**Status**: COMPLETED
**Completed**: December 28, 2025

**Deliverables**:

1. ✅ Initialize `BlobStorageService` in `DepotButlerWorkflow`
   - Added to `__init__` and `__aenter__` with graceful fallback
   - Disabled if `AZURE_STORAGE_CONNECTION_STRING` not configured
   - Non-blocking initialization (logs warning on failure)
2. ✅ Granular timestamp tracking implemented:
   - `downloaded_at` - Set when PDF downloaded from website
   - `email_sent_at` - Set after successful email delivery
   - `onedrive_uploaded_at` - Set after successful OneDrive upload
   - All timestamps stored in UTC via MongoDB EditionRepository
3. ✅ Updated `PublicationProcessingService`:
   - Added `blob_service` parameter to `__init__`
   - Integrated timestamp tracking in download/email/upload flows
   - Timestamps only set on successful operations
4. ✅ Test fixtures updated:
   - Added `blob_service=None` to `workflow_with_services` fixture
   - Added `blob_service=None` to `workflow_with_services_dry_run` fixture
   - All 227 unit tests passing
5. ✅ Repository methods utilized:
   - `mark_edition_processed()` - Creates/updates edition record with `downloaded_at`
   - `update_email_sent_timestamp()` - Sets timestamp after email success
   - `update_onedrive_uploaded_timestamp()` - Sets timestamp after upload success

**Key Implementation Details**:

- BlobStorageService initialization uses `settings.blob_storage.is_configured()` check
- Graceful degradation: workflow continues without blob storage if not configured
- Timestamp tracking uses `datetime.now(UTC)` for consistency
- MongoDB EditionRepository accessed via `get_mongodb_service()` singleton
- Edition key generated via `edition_tracker._generate_edition_key(edition)`

**Files Modified**:

- `src/depotbutler/workflow.py` - Initialize blob service, pass to processor
- `src/depotbutler/services/publication_processing_service.py` - Timestamp tracking
- `tests/conftest.py` - Updated test fixtures

**Commits**: TBD (to be committed)

**Next Steps**: Phase 5.3 - Blob archival step and historical collection script

---

### Phase 5.3: Blob Archival & Cache ✅ COMPLETE (90%)

**Status**: MOSTLY COMPLETE
**Completed**: December 28, 2025
**Deferred**: Historical collection script (Task 3) - 4-5 hours, separate session

**Deliverables**:

1. ✅ Implemented `_archive_to_blob_storage()` method in `PublicationProcessingService`
   - Archives PDF to blob storage after successful email/OneDrive delivery
   - Non-blocking error handling (logs warning, workflow continues)
   - Updates MongoDB with blob metadata (URL, path, container, size)
   - Sets `archived_at` timestamp in UTC
2. ✅ Implemented `--use-cache` (`-c`) CLI flag
   - Added flag parsing in `main.py`
   - Enhanced `_download_edition()` to check blob cache first when `use_cache=True`
   - Falls back to website download on cache miss
   - Gracefully handles missing blob service (auto-disabled cache)
3. ⏳ **DEFERRED**: Historical collection script (`scripts/collect_historical_pdfs.py`)
   - Estimated 4-5 hours of focused work
   - Will be tackled in separate dedicated session
   - Features planned:
     - Discover all editions using `HttpxBoersenmedienClient`
     - Check which editions already archived using `BlobStorageService.exists()`
     - Download missing editions and archive to Blob Storage
     - Update `processed_editions` collection with metadata
     - Progress reporting (X of Y editions processed)
     - Date range filtering, publication filtering, dry-run mode
     - Parallel downloads with configurable concurrency
     - Error handling and resume capability
4. ✅ Comprehensive test suite for blob archival
   - Created `tests/test_blob_archival.py` with 8 unit tests
   - `TestBlobArchival` class (4 tests):
     - Archive success path with full workflow
     - Disabled blob service scenario
     - Dry-run mode behavior
     - Non-blocking error handling
   - `TestCacheFunctionality` class (4 tests):
     - Cache hit skips download
     - Cache miss falls back to website download
     - Cache disabled always downloads
     - Graceful degradation with no blob service
   - All tests passing
5. ✅ Updated MASTER_PLAN.md to document Phase 5.3 completion

**Key Implementation Details**:

- **Non-blocking archival**: If blob archival fails, error is logged but workflow continues (email/OneDrive delivery unaffected)
- **Cache logic**: When `use_cache=True`, checks blob storage before downloading from website
- **Graceful degradation**: If `BlobStorageService` not initialized, archival is skipped and cache is disabled
- **MongoDB updates**: `update_blob_metadata()` stores blob URL, path, container name, file size, and archived timestamp

**Files Modified**:

- `src/depotbutler/main.py` - Added `--use-cache` flag parsing
- `src/depotbutler/workflow.py` - Pass `use_cache` to `PublicationProcessingService`
- `src/depotbutler/services/publication_processing_service.py` - Archival and cache logic
- `tests/test_blob_archival.py` - New comprehensive test suite (8 tests)
- `tests/conftest.py` - Updated fixtures with `use_cache=False`
- `tests/test_main.py` - Fixed assertions for new parameter

**Usage**:

```powershell
# Normal workflow (downloads from website, archives to blob)
python -m depotbutler

# Use cached PDFs if available (avoids re-download)
python -m depotbutler --use-cache

# Dry-run with cache (no emails/uploads, just tests cache logic)
python -m depotbutler --dry-run --use-cache
```

**Commits**: `1390620` (archival + cache implementation), `TBD` (test suite + docs)

---

### Phase 5.4: Testing & Validation ✅ COMPLETE

**Status**: COMPLETE
**Completed**: December 28, 2025

**Tasks Completed**:

1. ✅ Verified Azure Storage connection and blob service initialization
2. ✅ **End-to-end blob archival tested** with real edition (Megatrend Folger 51/2025)
3. ✅ Validated Azure Storage account setup (`depotbutlerarchive`)
4. ✅ Confirmed all granular timestamps working correctly
5. ✅ Verified MongoDB blob metadata complete and accurate
6. ✅ Fixed redundant `discover_subscriptions()` call in workflow
7. ⏳ **Deferred**: Historical script testing (script not yet built - Phase 5.3 Task 3)
8. ⏳ **Deferred**: Cost verification (requires >1 month of operation)

**End-to-End Test Results** (Megatrend Folger 51/2025):

**Full Workflow Execution**:

```test
📄 Edition: Megatrend Folger 51/2025
   Downloaded at:         2025-12-28 13:36:24
   Email sent at:         2025-12-28 13:36:25
   OneDrive uploaded at:  2025-12-28 13:36:30
   ✓ Archived at:         2025-12-28 13:36:31  ← Blob storage!
   Processed at:          2025-12-28 13:36:31
```

**Blob Metadata in MongoDB**:

- ✅ Blob URL: `https://depotbutlerarchive.blob.core.windows.net/editions/2025/megatrend-folger/2025-12-18_Megatrend-Folger_51-2025.pdf`
- ✅ Blob Path: `2025/megatrend-folger/2025-12-18_Megatrend-Folger_51-2025.pdf`
- ✅ Container: `editions`
- ✅ File Size: 699,641 bytes (0.67 MB)

**Workflow Logs Confirmed**:

```text
☁️ Archiving to blob storage...
✓ Archived to blob storage: 2025/megatrend-folger/2025-12-18_Megatrend-Folger_51-2025.pdf
  URL: https://depotbutlerarchive.blob.core.windows.net/editions/...
  Size: 699,641 bytes
✓ Blob metadata recorded in MongoDB
```

**Azure Storage Configuration**:

- ✅ Storage Account: `depotbutlerarchive` (Germany West Central, Cool tier)
- ✅ Container: `editions` (exists and accessible)
- ✅ Connection string configured in environment
- ✅ Blob service initializes successfully: `✓ Blob storage service initialized [container=editions]`

**Code Quality**:

- ✅ 271 unit tests passing (including 8 new blob archival tests)
- ✅ `_archive_to_blob_storage()` method with non-blocking error handling
- ✅ `_download_edition()` checks cache when `use_cache=True`
- ✅ MongoDB metadata updates working correctly

**Bug Fixes**:

- ✅ Removed redundant `discover_subscriptions()` call (was called twice: once before sync, once during sync)

**Test Scripts Created**:

- `scripts/test_archival_setup.py` - Deactivate recipients and clear edition for testing
- `scripts/verify_archival.py` - Verify blob metadata and timestamps in MongoDB
- `scripts/check_edition_metadata.py` - Check specific edition metadata
- `scripts/force_reprocess_edition.py` - Force reprocess for testing

**Success Criteria Met**:

- ✅ PDFs successfully archived to Azure Blob Storage (real 0.67 MB PDF)
- ✅ All granular timestamps recorded correctly (download, email, upload, archive)
- ✅ Cache retrieval implementation complete (`--use-cache` flag)
- ✅ Non-blocking archival (workflow continues on blob failures)
- ✅ Graceful degradation (works without blob storage configured)
- ⏳ Cache hit scenario (deferred - requires new edition or reprocessing)
- ⏳ Historical collection script (deferred - 4-5 hours work)
- ⏳ Cost verification (deferred - requires 30 days operational data)

**Commits**: `0ceca80` (test suite + docs), `fc1cd19` (Phase 5.4 completion), `d7668af` (redundancy fix)

---

### Sprint 6: Data Quality & User Experience ✅

**Completed**: December 29, 2025
**Duration**: 1 day

**Objectives**:

- Improve blob storage metadata quality (German umlaut conversion)
- Enhance admin notifications (OneDrive link usability)
- Centralize sanitization logic (DRY principle)

**Deliverables**:

1. ✅ **Centralized German Umlaut Conversion**
   - Moved conversion logic from `utils/helpers.py` to `BlobStorageService`
   - Single source of truth for metadata sanitization
   - Consistent handling across all blob operations
   - Removed duplicated code from filename generation

2. ✅ **Enhanced OneDrive Notifications**
   - Modified `NotificationService.compose_upload_links()` to return clickable links
   - Previously: Only first upload was clickable, others were plain text
   - Now: All OneDrive locations are clickable links (multiple recipients)
   - Better user experience for admins checking upload status

3. ✅ **Code Quality Improvements**
   - Reduced duplication with centralized sanitization
   - Better separation of concerns (blob service owns metadata rules)
   - Maintained 100% backward compatibility
   - All 376 tests passing

**Technical Details**:

- **German Umlaut Mapping**: Ä→Ae, Ö→Oe, Ü→Ue, ß→ss (preserves meaning, meets HTTP header requirements)
- **Blob Metadata Sanitization**: Converts characters to ASCII-safe alternatives (ö→oe, é→e, etc.)
- **OneDrive Links**: HTML `<a>` tags with full URLs for all upload locations
- **Test Coverage**: No new tests required (existing tests validate changes)

**Key Files Modified**:

- `src/depotbutler/services/blob_storage_service.py` - Added `_sanitize_metadata_value()`
- `src/depotbutler/utils/helpers.py` - Removed umlaut conversion (now delegated)
- `src/depotbutler/mailer/composers/notification_service.py` - Enhanced link formatting
- `docs/SPRINT6_IMPROVEMENTS.md` - Created comprehensive sprint documentation

**Benefits**:

- **Better metadata**: Azure Blob Storage metadata now compliant with HTTP header specs
- **Better UX**: Admin notifications with clickable links save time
- **Better code**: Single responsibility, less duplication, easier maintenance

**Commits**: `ca24a49` (Sprint 6 code changes)

**Documentation**: See [SPRINT6_IMPROVEMENTS.md](SPRINT6_IMPROVEMENTS.md) for detailed technical analysis

---

### Sprint 7: Historical PDF Collection & URL Enrichment ✅

**Completed**: January 4, 2026
**Duration**: 6 days

**Objectives**:

- Import historical PDFs from OneDrive with correct publication dates
- Enrich MongoDB and blob storage with download URLs from website
- Ensure complete consistency with regular scheduled workflow

**Scope & Two-Script Strategy**:

- ✅ **Script 1 (PRIMARY)**: `import_from_onedrive.py` - Import from OneDrive, establish correct dates
  - Source: Local OneDrive folder with standardized filenames
  - Contains CORRECT publication dates from PDF headers
  - Issue-based edition keys (reliable, not affected by date discrepancies)
- ✅ **Script 2 (SUPPLEMENTAL)**: `sync_web_urls.py` - Add website download URLs
  - Fetches download URLs for all editions available on boersenmedien.com
  - Updates MongoDB `download_url` field for matching editions
  - Updates blob storage metadata tags with download URL
  - Does NOT modify dates (preserves OneDrive import accuracy)
- ✅ **Legacy Script**: `collect_historical_pdfs.py` - Website-first approach (deprecated in favor of OneDrive import)

**Deliverables**:

1. ✅ **OneDrive Import Script** (`scripts/import_from_onedrive.py` - 557 lines) - COMPLETE
   - Parses standardized filenames: `YYYY-MM-DD_Edition-Name_II-YYYY.pdf`
   - Issue-based edition keys (top-down: `year_issue_publication`)
   - Handles both old name ("Die-800%-Strategie") and new name ("Megatrend-Folger")
   - Archives PDFs to blob storage from local OneDrive folder
   - Creates MongoDB entries with `source="onedrive_import"`
   - Dry-run mode, year range filtering, progress reporting
   - Preserves correct publication dates from PDF filenames
   - **Production Results**: 607 editions imported successfully

2. ✅ **Download URL Enrichment Script** (`scripts/sync_web_urls.py` - 728 lines) - COMPLETE
   - Discovers ALL editions available on website (paginated discovery)
   - For each web edition, finds matching MongoDB entry (by publication_date matching)
   - Updates MongoDB `download_url` field for matched editions
   - Updates blob storage metadata tags with download URL
   - Handles date discrepancies (web dates may differ from PDF dates)
   - Dry-run mode, progress reporting, error handling
   - Does NOT modify publication dates (preserves OneDrive import accuracy)
   - **Production Results**: 379 editions enriched with download URLs (62.6% of total, 95.9% of web-available)

3. ✅ **Blob Metadata Remediation Script** (`scripts/update_blob_metadata.py`) - ONE-TIME USE
   - Backfilled blob metadata when sync script couldn't update due to missing MongoDB `onedrive_path` field
   - Found blobs by publication_date prefix matching
   - Successfully updated 380/380 blob metadata entries
   - Deleted after successful execution (one-time remediation)

**Production Execution Results**:

**OneDrive Import** (Megatrend Folger):

- Total editions processed: 607 (2014-2025)
- Successful imports: 607 ✅
- Failed imports: 0
- Skipped (duplicates): 0
- MongoDB entries created: 607
- Blob storage archives: 607
- Duration: ~30 minutes

**URL Enrichment** (Megatrend Folger):

- Total MongoDB entries: 607
- Web editions discovered: 397 (2019-2025)
- Successful matches: 379 (95.9% match rate)
- Failed matches: 0
- Skipped (no URL on website): 228 (2014-2018 archives not on website)
- MongoDB updates: 379
- Blob metadata updates: 380 (includes 1 pre-existing)
- Duration: ~7 seconds processing after ~5 minutes web scraping

**Validation Results**:

- ✅ MongoDB: 380/607 entries have `download_url` (62.6%)
- ✅ Blob Storage: 380/607 blobs have `download_url` in metadata (62.6%)
- ✅ Archives without URLs: 227 (2014-2018, correctly not on website)
- ✅ Sample inspection: All URLs valid, timestamps correct
- ✅ No data loss or corruption

**Test Coverage**:

- ✅ Added 5 comprehensive tests for `BlobStorageService.update_metadata()` method
- ✅ All 401 unit tests passing (including new tests)
- ✅ 92% code coverage for blob_storage_service module
- ✅ Tests cover: success, blob not found, metadata merging, German umlaut sanitization, error handling

**Key Technical Achievements**:

- ✅ **Publication date matching**: Used `publication_date` field for reliable matching (95.9% success rate)
- ✅ **Issue-based edition keys**: Reliable tracking independent of date discrepancies
- ✅ **Standardized filenames**: YYYY-MM-DD_Edition-Name_II-YYYY.pdf format
- ✅ **Publication name mapping**: Handles "Die-800%-Strategie" → "Megatrend-Folger" rename
- ✅ **Source tracking**: `source` field distinguishes onedrive_import vs scheduled_job vs web_historical
- ✅ **Download URL enrichment**: Updates existing records without modifying dates
- ✅ **Blob metadata updates**: Conditional updates preserve existing metadata, add web sync timestamps
- ✅ **German umlaut sanitization**: Azure Blob Storage ASCII compliance (Ä→Ae, ö→oe, etc.)

**Key Technical Challenges & Solutions**:

1. **Date Discrepancies**: Website shows delivery dates, PDFs contain actual publication dates
   - ✅ Solution: OneDrive import establishes correct dates, URL enrichment preserves them

2. **Blob Metadata Update Issue**: Sync script couldn't update blob metadata due to missing `onedrive_path` field in MongoDB
   - ✅ Root Cause: Sync script required `onedrive_path` from MongoDB to locate blobs
   - ✅ Reality: Blobs have `onedrive_file_path` in metadata, MongoDB entries lack `onedrive_path`
   - ✅ Solution: Created `update_blob_metadata.py` for one-time remediation using publication_date prefix matching
   - ✅ Result: 380/380 blob metadata entries successfully updated

3. **Metadata Consistency**: Both scripts must produce identical MongoDB/blob structure
   - ✅ Solution: Use same helpers (create_filename, normalize_edition_key, sanitize metadata)

**Scripts Cleanup**:

- ✅ Deleted 9 one-time validation/remediation scripts:
  - `check_url_updates.py` - Sprint 7 MongoDB validation
  - `check_megatrend_urls.py` - Sprint 7 publication-specific validation
  - `check_blob_metadata.py` - Sprint 7 blob storage validation
  - `check_onedrive_paths.py` - Sprint 7 investigation script
  - `update_blob_metadata.py` - Sprint 7 one-time remediation
  - `delete_test_edition.py` - Test cleanup
  - `reset_archive.py` - Obsolete
  - `cleanup_blob_and_editions.py` - One-time cleanup
  - `enrich_download_urls.py` - Superseded by sync_web_urls.py

**Production Readiness Checklist**:

✅ OneDrive import script: Functional, tested, executed
✅ Execute OneDrive import: Complete (607 editions)
✅ Download URL enrichment script: Functional, tested, executed
✅ Execute URL enrichment: Complete (379 editions)
✅ Blob metadata remediation: Complete (380 blobs)
✅ Full validation: Complete (MongoDB + blob storage)
✅ Type safety: mypy compliant
✅ Code quality: Follows project conventions
✅ Test coverage: 5 new tests, 401 total passing
✅ Documentation: Comprehensive docstrings, usage examples
✅ Scripts cleanup: 9 obsolete scripts deleted

**Usage Examples**:

```powershell
# STEP 1: Import from OneDrive (PRIMARY SOURCE - correct dates)
# Dry-run first to preview
uv run python scripts/import_from_onedrive.py --dry-run

# Execute full import
uv run python scripts/import_from_onedrive.py

# Or import specific year range
uv run python scripts/import_from_onedrive.py --start-year 2020 --end-year 2023

# STEP 2: Enrich with download URLs (SUPPLEMENTAL - website links)
# Dry-run first to preview
uv run python scripts/sync_web_urls.py --publication megatrend-folger --dry-run

# Execute full enrichment
uv run python scripts/sync_web_urls.py --publication megatrend-folger

# Or sync all active publications
uv run python scripts/sync_web_urls.py --all
```

**Commits**: TBD (Sprint 7 completion)

**Status**: ✅ COMPLETE - All objectives achieved, production execution successful

---

### Sprint 9: Monitoring & Observability (Minimal Version) ✅

**Completed**: January 4, 2026
**Duration**: ~4 hours (Minimal Version)
**Status**: ✅ COMPLETE

**Objectives**:

- Add correlation IDs for tracing individual workflow runs
- Collect timing metrics for all workflow operations
- Track errors and save to MongoDB for analysis
- Create query script for viewing metrics

**Deliverables**:

1. ✅ **Correlation ID Management** (`src/depotbutler/observability/correlation.py`)
   - UUID-based correlation IDs with timestamp format: `run-YYYYMMDD-HHMMSS`
   - Thread-safe context management using `contextvars`
   - Functions: `generate_correlation_id()`, `get_correlation_id()`, `set_correlation_id()`
   - Enables tracing all logs for a specific workflow run

2. ✅ **Metrics Tracking Module** (`src/depotbutler/observability/metrics.py`)
   - `WorkflowMetrics` Pydantic model: run_id, duration, operations, editions_processed, errors_count
   - `WorkflowError` Pydantic model: run_id, error_type, error_message, operation, context
   - `MetricsTracker` class: timing, error tracking, MongoDB persistence
   - Methods: `start_timer()`, `stop_timer()`, `record_error()`, `save_to_mongodb()`

3. ✅ **Workflow Integration** (`src/depotbutler/workflow.py`)
   - Correlation ID generation at workflow start
   - Timing for operations: initialization, publication_processing, notification
   - Edition counting per workflow run
   - Error tracking with context
   - Metrics saved to MongoDB after each run (with graceful error handling)

4. ✅ **MongoDB Collections** (created on first use)
   - `workflow_metrics` - Stores WorkflowMetrics documents
   - `workflow_errors` - Stores WorkflowError documents
   - Indexed by timestamp for efficient querying

5. ✅ **Query Script** (`scripts/view_metrics.py` - 241 lines)
   - View recent runs: `uv run python scripts/view_metrics.py --last 10`
   - View errors: `uv run python scripts/view_metrics.py --errors-only --hours 24`
   - Statistics: `uv run python scripts/view_metrics.py --stats --days 7`
   - Displays: duration, editions processed, errors, operation breakdown

6. ✅ **Test Coverage** (20 new tests)
   - `tests/test_observability_correlation.py` (5 tests) - Correlation ID generation, context management
   - `tests/test_observability_metrics.py` (15 tests) - MetricsTracker, timing, error recording, MongoDB persistence
   - All 423 tests passing (401 before + 20 new + 2 existing updated)

**Key Implementation Details**:

- **Correlation IDs**: Appear in all logs as `[run-20260104-183045]` prefix
- **Timing**: Uses Python `time.time()` for operation duration measurement
- **Error Tracking**: Captures exception type, message, operation, and custom context
- **Non-blocking Metrics**: If metrics save fails, workflow continues (logged as warning)
- **Graceful Degradation**: Metrics work even if MongoDB temporarily unavailable

**Usage Examples**:

```powershell
# Run workflow (metrics collected automatically)
python -m depotbutler

# View last 10 runs
uv run python scripts/view_metrics.py --last 10

# Show errors from last 24 hours
uv run python scripts/view_metrics.py --errors-only --hours 24

# Calculate statistics for last 7 days
uv run python scripts/view_metrics.py --stats --days 7
```

**Benefits**:

- **Traceability**: Correlation IDs allow following a single run through all logs
- **Performance Insights**: Answer "How long does processing take?" and "Which operation is slow?"
- **Error Visibility**: See all errors in one place, not scattered through logs
- **Data-Driven Optimization**: Metrics reveal bottlenecks and trends

**Deferred (Full Version - ~4 more hours)**:

- [ ] Streamlit dashboard for visualization
- [ ] Enhanced logging format with correlation IDs in formatter
- [ ] Alerting on error thresholds
- [ ] Performance trend analysis
- [ ] Real-time monitoring

**Files Created/Modified**:

- `src/depotbutler/observability/__init__.py` - Package exports
- `src/depotbutler/observability/correlation.py` - Correlation ID management (73 lines)
- `src/depotbutler/observability/metrics.py` - Metrics tracking (129 lines)
- `src/depotbutler/workflow.py` - Metrics integration
- `scripts/view_metrics.py` - Query script (241 lines)
- `tests/test_observability_correlation.py` - 5 tests
- `tests/test_observability_metrics.py` - 15 tests

**Commits**: TBD (to be committed)

**Status**: ✅ COMPLETE - Minimal version provides 80% of value in 1 day

---

## Near-Term Sprints (8-10)

### Sprint 8: Publication Preference Management Tools ✅

**Status**: COMPLETE
**Completion Date**: January 4, 2026
**Duration**: ~3 hours

**Objectives**:

- Admin tools for managing recipient preferences
- Bulk preference updates
- Reporting on preference distribution

**Deliverables**:

1. ✅ `scripts/manage_recipient_preferences.py` (687 lines)
   - Add/remove publication preferences for specific recipient
   - List current preferences for recipient
   - Bulk operations: add/remove publication to/from ALL recipients
   - User activation/deactivation (single and bulk)
   - Show statistics: coverage, delivery methods, warnings
   - Comprehensive help and argument parsing

2. ✅ `scripts/check_recipients.py` enhancements
   - Added `--stats` flag for detailed preference statistics
   - Added `--coverage` flag for per-publication coverage only
   - New `show_preference_statistics()` function
   - Per-publication coverage with emoji status icons
   - Delivery method statistics (email-only, upload-only, both, neither)
   - Warnings for recipients without preferences

3. ✅ Comprehensive test suite
   - `tests/test_manage_recipient_preferences.py` (509 lines, 16 tests)
   - Tests for all CRUD operations (add, remove, list)
   - Tests for bulk operations
   - Tests for statistics display
   - All tests passing with proper mocking

**Key Features**:

- **Single Operations**:
  - `add user@example.com megatrend-folger` - Add preference to recipient
  - `remove user@example.com megatrend-folger` - Remove preference from recipient
  - `list user@example.com` - Show all preferences for recipient
  - `activate user@example.com` - Activate specific user
  - `deactivate user@example.com` - Deactivate specific user

- **Bulk Operations**:
  - `bulk-add megatrend-folger` - Add to ALL active recipients
  - `bulk-remove megatrend-folger` - Remove from ALL recipients (active/inactive)
  - `bulk-activate` - Activate ALL inactive users
  - `bulk-deactivate` - Deactivate ALL active users
  - Progress output with emoji indicators (✅ added/activated, ⏭️ skipped, ❌ failed)

- **Statistics & Reporting**:
  - `stats` - Show comprehensive statistics (recipients, coverage, delivery methods)
  - `--coverage` - Quick per-publication coverage view
  - Warnings for recipients without preferences
  - Per-publication recipient counts and coverage percentages

**Usage Examples**:

```powershell
# Add preference with custom delivery settings
uv run python scripts/manage_recipient_preferences.py add user@example.com aktionaer-epaper --no-email

# List all preferences for a recipient
uv run python scripts/manage_recipient_preferences.py list user@example.com

# Bulk add publication to all active recipients
uv run python scripts/manage_recipient_preferences.py bulk-add megatrend-folger

# Activate/deactivate specific user
uv run python scripts/manage_recipient_preferences.py activate user@example.com
uv run python scripts/manage_recipient_preferences.py deactivate user@example.com

# Bulk activate/deactivate all users
uv run python scripts/manage_recipient_preferences.py bulk-activate
uv run python scripts/manage_recipient_preferences.py bulk-deactivate

# Show preference statistics
uv run python scripts/manage_recipient_preferences.py stats

# Enhanced check_recipients with statistics
uv run python scripts/check_recipients.py --stats
uv run python scripts/check_recipients.py --coverage
```

**Benefits**:

- **Operational Efficiency**: Quickly manage preferences and user status for individual or all recipients
- **User Management**: Enable/disable recipients without deleting data or preferences
- **Visibility**: Clear reporting on who receives what publications
- **Data Quality**: Identify recipients without preferences (potential issues)
- **Audit Trail**: Console output documents all operations performed
- **Testing**: Full test coverage ensures reliability of admin operations

**Files Created/Modified**:

- **Created**:
  - `scripts/manage_recipient_preferences.py` (687 lines, 10 commands)
  - `tests/test_manage_recipient_preferences.py` (509 lines, 16 tests)
- **Modified**:
  - `scripts/check_recipients.py` (+157 lines, added statistics functions)
  - `docs/MASTER_PLAN.md` (this file, Sprint 8 section)

**Commits**:

- `9a0baef` - Sprint 8: Admin Tools for Recipient Preference Management
- TBD - Sprint 8 Extension: User Activation/Deactivation Management

---

### Sprint 10: Monitoring & Observability (Full Version) ⏳

**Status**: PLANNED (Sprint 9 Minimal Version Complete)
**Priority**: Low
**Estimated Duration**: 1 day

**Objectives**:

- Add visualization dashboard for metrics
- Enhanced logging format with correlation IDs
- Alerting on error thresholds

**Deliverables (building on Sprint 9)**:

1. [ ] Streamlit dashboard for metrics visualization
   - Publication processing time
   - API response times
   - Upload speeds
3. [ ] Error aggregation and reporting
4. [ ] Optional: Application Insights integration
5. [ ] Dashboard for key metrics (Streamlit or simple HTML)

---

### Sprint 12: Deployment & CI/CD Improvements ⏳

**Status**: PLANNED
**Priority**: Low
**Estimated Duration**: 1 day

**Objectives**:

- Streamline deployment process
- Improve CI/CD pipeline
- Environment configuration management

**Deliverables**:

1. [ ] Docker image optimization (reduce size)
2. [ ] Multi-environment support (dev/staging/prod)
3. [ ] Automated deployment script improvements
4. [ ] Secrets management review
5. [ ] Rollback procedures documented

---

### Sprint 11: Documentation & Knowledge Base ✅

**Status**: COMPLETE
**Completion Date**: January 4, 2026
**Duration**: ~2 hours

**Objectives**:

- Consolidate documentation
- Create troubleshooting guides
- Document operational procedures

**Deliverables**:

1. ✅ **ARCHITECTURE_DIAGRAMS.md** (420 lines)
   - 10 comprehensive Mermaid diagrams:
     * System overview
     * Clean architecture layers
     * Workflow execution sequence
     * Data model (ER diagram)
     * Authentication & security flow
     * Publication processing state machine
     * OneDrive upload strategy
     * Admin scripts ecosystem
     * Error handling & monitoring
     * Deployment architecture
   - Visual documentation of entire system
   - Links to detailed documentation

2. ✅ **TROUBLESHOOTING.md** (650 lines)
   - Quick reference table for common issues
   - Authentication issues (cookie, OneDrive)
   - Database issues (connection, collections)
   - Download issues (edition not found, timeouts)
   - Email issues (not sent, too large)
   - Upload issues (OneDrive failures)
   - Testing issues (tests failing, pre-commit)
   - Production issues (workflow not running)
   - Performance issues
   - Data issues (recipient not receiving)
   - Common error messages reference
   - Getting help section with admin scripts

3. ✅ **OPERATIONAL_RUNBOOK.md** (550 lines)
   - Daily operations (morning check, new editions)
   - Weekly tasks (health check, cookie check, database maintenance)
   - Monthly tasks (subscription review, recipient audit, backups)
   - Emergency procedures (critical failures, auth expired, email/upload failures)
   - Monitoring & alerts (key metrics, setup)
   - Incident response (log template, post-mortem)
   - Maintenance windows
   - Contacts and escalation

4. ✅ **DOCUMENTATION_INDEX.md** (380 lines)
   - Central documentation hub
   - Organized by category (Architecture, Operations, Setup, Development)
   - "I want to..." use case guide
   - Recent updates section
   - Documentation status table
   - Contributing guidelines

5. ✅ **This master plan** (kept updated!)

**Key Features**:

- **Visual Documentation**: 10 Mermaid diagrams cover all major system aspects
- **Troubleshooting**: Symptoms → Diagnosis → Solution format for 15+ issue types
- **Operations**: Daily/weekly/monthly procedures for smooth operations
- **Emergency Response**: Step-by-step procedures for critical failures
- **Navigation**: Comprehensive index with use-case-based navigation
- **Standards**: Documentation standards and contribution guidelines

**Benefits**:

- **Reduced Onboarding Time**: New admins can understand system quickly with visual diagrams
- **Faster Problem Resolution**: Troubleshooting guide provides step-by-step solutions
- **Operational Excellence**: Runbook ensures consistent daily/weekly procedures
- **Knowledge Retention**: All operational knowledge now documented
- **Maintainability**: Central index makes finding information easy

**Files Created**:

- `docs/ARCHITECTURE_DIAGRAMS.md` (420 lines, 10 diagrams)
- `docs/TROUBLESHOOTING.md` (650 lines, 15+ issue types)
- `docs/OPERATIONAL_RUNBOOK.md` (550 lines, daily/weekly/monthly tasks)
- `docs/DOCUMENTATION_INDEX.md` (380 lines, central hub)

**Files Modified**:

- `docs/MASTER_PLAN.md` (this file, Sprint 11 section)

**Commits**: TBD (to be committed)

---

## Future Vision (Phases 1-4)

These phases represent longer-term features that transform DepotButler from a distribution service into a comprehensive portfolio tracking and analysis system.

### Phase 1: PDF Data Extraction & Portfolio Tracking

**Status**: PLANNED (Q1 2026)
**Priority**: High for analytics use case
**Estimated Duration**: 3-4 weeks

**Objectives**:

- Extract structured data from Megatrend-Folger PDFs
- Build temporal database of portfolio history (15 years)
- Track warrant positions and changes over time

**Key Features**:

1. PDF table extraction with `pdfplumber`
2. Parse warrant details (WKN, name, purchase date, price, quantity, target)
3. Detect BUY/SELL transactions between editions
4. Store depot snapshots with temporal validity
5. Backfill script for 15 years of historical PDFs

**Data Model**:

```javascript
// depots collection
{
  valid_from: ISODate("2025-12-23"),
  valid_until: ISODate("2025-12-30"),  // null = current
  publication_id: "megatrend-folger",
  publication_date: ISODate("2025-12-23"),
  warrants: [
    {
      wkn: "AB1234",
      name: "Call-Warrant auf SAP",
      underlying: "SAP",
      purchase_date: ISODate("2025-01-15"),
      purchase_price: 12.50,
      quantity: 100,
      target_price: 25.00,
      stop_loss: 8.00
    }
  ],
  total_positions: 25,
  changes: {  // vs previous edition
    new_positions: ["AB1234"],
    closed_positions: ["XY9999"],
    quantity_changes: {"CD5678": +50}
  }
}
```

**Dependencies**:

- `pdfplumber>=0.11.8` for PDF parsing
- Sample PDFs for testing parsing logic
- Decision on handling OCR errors in old PDFs

**Deliverables**:

1. `PDFExtractionService` - Extract depot tables from PDFs
2. `DepotTrackingService` - Manage temporal snapshots
3. `DepotRepository` - CRUD for depot data
4. Backfill script for historical data
5. Change detection algorithm
6. Data validation rules

**Success Metrics**:

- 100% of historical PDFs processed successfully
- Change detection accuracy >95%
- Processing time <2 seconds per PDF

---

### Phase 2: Intraday Price Tracking

**Status**: PLANNED (Q1-Q2 2026)
**Priority**: Medium
**Estimated Duration**: 2 weeks

**Objectives**:

- Fetch real-time/intraday prices for active warrants
- Build price history database
- Enable performance calculations

**Key Features**:

1. yfinance integration for price data
2. Hourly price fetching during trading hours
3. Price history storage (time-series data)
4. Fallback to underlying stock prices
5. API rate limiting and retry logic

**Data Model**:

```javascript
// price_data collection (time-series)
{
  wkn: "AB1234",
  timestamp: ISODate("2025-12-27T14:30:00Z"),
  price: 15.75,
  underlying_price: 207.50,  // if warrant price unavailable
  volume: 1250,
  source: "yfinance",  // or "boerse-frankfurt"
  validity: "current"  // or "historical"
}
```

**Technical Challenges**:

- yfinance is unofficial (could break)
- Not all warrants have public tickers
- API rate limits (~2000 requests/hour)

**Deliverables**:

1. `PriceFetcherService` - Fetch prices from APIs
2. `PriceRepository` - Store price data
3. Scheduled job for intraday fetching (Azure Container Apps)
4. Price cache with TTL (5 minutes)
5. Fallback to multiple data sources

**Success Metrics**:

- Intraday prices fetched with <1% failure rate
- API response time <2 seconds per WKN
- Data latency <5 minutes

---

### Phase 3: Analytics Dashboard

**Status**: PLANNED (Q2 2026)
**Priority**: Low (nice-to-have)
**Estimated Duration**: 2-3 weeks

**Objectives**:

- Web dashboard for portfolio visualization
- Historical performance analysis
- Interactive charts and reports

**Key Features**:

1. Streamlit-based dashboard
2. Portfolio value over time chart
3. Top performers / worst performers
4. Buy/sell transaction history
5. Current holdings snapshot
6. Historical depot composition

**Tech Stack**:

- Streamlit (Python web framework)
- Plotly for interactive charts
- Pandas for data manipulation
- Deploy on Azure Container Apps

**Pages**:

1. **Overview** - Current portfolio value, P&L, positions
2. **History** - 15-year timeline with annotations
3. **Positions** - Detailed warrant information
4. **Analytics** - Correlation, drawdown, Sharpe ratio
5. **Transactions** - All buy/sell history

**Deliverables**:

1. Streamlit app with multiple pages
2. Chart components (line, bar, pie)
3. Data aggregation services
4. Deployment configuration
5. User authentication (optional)

**Success Metrics**:

- Dashboard loads in <2 seconds
- Charts render smoothly for 15 years of data
- Can answer: "What was my portfolio value on date X?"

---

### Phase 4: Machine Learning & Recommendations

**Status**: PLANNED (Q3 2026+)
**Priority**: Low (research project)
**Estimated Duration**: 4-6 weeks

**Objectives**:

- ML-based insights and recommendations
- Pattern recognition in trading behavior
- Predictive analytics

**Potential Features**:

1. Optimal holding period prediction
2. Success pattern detection (what works?)
3. Risk assessment per position
4. Portfolio optimization suggestions
5. Anomaly detection (unusual trades)

**Tech Stack**:

- scikit-learn for ML models
- TensorFlow/PyTorch (if needed)
- MLflow for experiment tracking
- Azure ML (optional)

**Research Questions**:

- What characteristics define successful warrant trades?
- Is there a pattern to entry/exit timing?
- Can we predict which sectors perform best?
- How does portfolio diversification impact returns?

**Deliverables**:

1. Data pipeline for ML features
2. Exploratory data analysis notebooks
3. Trained ML models
4. Recommendation engine
5. A/B testing framework (future)

**Success Metrics**:

- Model accuracy >60% (better than random)
- Actionable insights generated
- User finds recommendations useful

---

## System Status (December 29, 2025)

### ✅ Currently Working

**Core Features**:

- Multi-publication processing (all active publications in one run)
- Publication auto-discovery and sync from website
- Edition tracking (prevents duplicates per publication)
- Email distribution to recipients
- OneDrive upload with folder organization
- Chunked upload optimization (10MB chunks, 28x faster)
- Smart filename generation (title case, readable)
- Consolidated notifications (single summary email with clickable links)
- Dry-run mode for safe testing
- MongoDB-driven configuration (dynamic)
- **Azure Blob Storage archival** (Cool tier, production validated) ✅
- **Cache retrieval** (`--use-cache` flag to avoid re-downloads) ✅
- **German umlaut conversion** (blob metadata sanitization) ✅
- **Historical PDF collection script** (618-line backfill tool) ✅

**Infrastructure**:

- Azure Container Apps deployment
- Scheduled jobs (daily execution)
- MongoDB Atlas database
- Azure Blob Storage (archival with metadata)
- GitHub Actions CI/CD

**Test Coverage**:

- 376 tests passing
- 76% code coverage
- Integration tests for multi-publication scenarios
- Blob storage archival tests (8 comprehensive tests)

---

### ❌ Not Yet Implemented

**Near-Term** (Sprints 8-10):

- Advanced recipient preference management tools
- Monitoring and observability enhancements
- Deployment automation improvements

**Long-Term** (Phases 1-4):

- PDF data extraction and parsing
- Portfolio tracking database
- Intraday price fetching
- Analytics dashboard
- ML-based recommendations

---

## Key Metrics & Performance

### Current Scale

- **Publications**: 2 active (Megatrend Folger, DER AKTIONÄR E-Paper)
- **Recipients**: ~5 (with per-publication preferences)
- **Editions Processed**: 50+ since deployment
- **Uptime**: 99%+ (daily scheduled job)

### Performance

- **Workflow Execution**: 30-90 seconds per run (2 publications)
- **File Upload**: 9 seconds for 64MB file (chunked)
- **Email Delivery**: <5 seconds per recipient
- **Discovery Sync**: <10 seconds

### Costs (Monthly)

- **Azure Container Apps**: €0 (free tier)
- **MongoDB Atlas**: €0 (free tier, 512MB)
- **Azure Blob Storage**: <€1 (Cool tier, ~1GB)
- **Total**: <€5/month

---

## Technology Stack

### Backend

- **Language**: Python 3.13
- **Framework**: Clean Architecture (domain/infrastructure/application layers)
- **Async**: httpx, motor (async MongoDB driver)
- **Validation**: Pydantic V2
- **Testing**: pytest, pytest-asyncio (241 tests, 72% coverage)

### Infrastructure

- **Cloud**: Microsoft Azure
- **Compute**: Azure Container Apps (scheduled jobs)
- **Database**: MongoDB Atlas (free tier)
- **Storage**: Azure Blob Storage (Cool tier)
- **CI/CD**: GitHub Actions

### External Services

- **Website**: boersenmedien.com (subscription data)
- **Email**: SMTP (GMX)
- **File Storage**: OneDrive (via Microsoft Graph API)

---

## Risk Assessment

### High Risk Items

1. **Cookie Authentication Expiry**
   - *Risk*: Cookie expires, workflow fails
   - *Mitigation*: 3-day expiration warnings, admin notifications
   - *Status*: Monitoring in place

2. **OneDrive API Rate Limiting**
   - *Risk*: Multiple uploads may hit rate limits
   - *Mitigation*: Chunked uploads, retry logic, sequential processing
   - *Status*: Mitigated with optimizations

3. **MongoDB Free Tier Limits**
   - *Risk*: 512MB storage limit exceeded
   - *Mitigation*: Monitor usage, archive old data, upgrade if needed
   - *Status*: Currently at ~100MB (safe)

### Medium Risk Items

1. **Website Structure Changes**
   - *Risk*: boersenmedien.com changes HTML structure
   - *Mitigation*: Discovery service has error handling, manual verification
   - *Status*: Monitoring enabled

2. **Azure Container Apps Free Tier**
   - *Risk*: Free tier quota exceeded (unlikely)
   - *Mitigation*: Monitor usage, move to paid tier if needed
   - *Status*: Well within limits

### Low Risk Items

1. **Timezone Handling**
   - *Risk*: Publication times vary
   - *Mitigation*: UTC timestamps everywhere, explicit timezone handling
   - *Status*: Documented and tested

2. **Email Deliverability**
   - *Risk*: Emails marked as spam
   - *Mitigation*: Test regularly, monitor bounce rates
   - *Status*: No issues so far

---

## Open Questions

### Sprint 5 (Blob Storage)

1. Should cached PDFs have TTL or kept indefinitely?
2. How many historical editions to collect initially? (All-time vs last year)
3. Cleanup policy for old PDFs in blob storage?

### Sprint 6+ (Preferences)

1. Admin UI needed or CLI sufficient?
2. Recipient onboarding process (how do they set preferences?)
3. Per-publication notification preferences?

### Phase 1+ (Data Extraction)

1. Where are 15 years of historical PDFs stored?
2. Are all historical PDFs the same format?
3. Manual data validation needed after backfill?
4. Should we use paid/official price APIs or accept unofficial ones?

---

## References

### Documentation

- **Architecture**: [architecture.md](architecture.md)
- **Business Requirements**: [BUSINESS_REQUIREMENTS.md](BUSINESS_REQUIREMENTS.md)
- **Code Quality**: [CODE_QUALITY.md](CODE_QUALITY.md)
- **Configuration**: [CONFIGURATION.md](CONFIGURATION.md)
- **Testing**: [TESTING.md](TESTING.md)
- **Deployment**: [DEPLOYMENT.md](DEPLOYMENT.md)
- **Session Status**: [SESSION_STATUS.md](SESSION_STATUS.md) (daily updates)
- **Validation Results**: [VALIDATION_RESULTS.md](VALIDATION_RESULTS.md)

### Key Scripts

- **Setup**: `scripts/setup_onedrive_auth.py`, `scripts/init_app_config.py`
- **Data**: `scripts/seed_publications.py`, `scripts/add_recipient_preferences.py`
- **Maintenance**: `scripts/update_cookie_mongodb.py`, `scripts/check_recipients.py`
- **Testing**: `scripts/test_dry_run.py`, `scripts/validation/`

### Git History

- **Sprint 1-2**: Multiple commits Dec 13-14, 2025
- **Sprint 3**: Commits `1c7193f`, `c5c20f1` (Dec 14, 2025)
- **Sprint 4**: Commits `ac3402a`, `04b678c`, `892b5a1`, `a05f3b4` (Dec 14, 2025)
- **Sprint 5**: Commits `cf843c9`, `1dab547`, `376faca`, `0bf7c7d` (Dec 27, 2025)

---

## How to Use This Plan

### For Daily Work

1. Check **Current Sprint** section for active tasks
2. Update **SESSION_STATUS.md** with daily progress
3. Mark tasks complete in this file as you finish them
4. Create new sprints as needed

### For Planning

1. Review **Near-Term Sprints** for next 1-2 months
2. Adjust priorities based on needs
3. Break down sprints into daily tasks
4. Estimate effort and set target dates

### For Long-Term Vision

1. Review **Future Vision** phases
2. Validate assumptions and requirements
3. Adjust based on feedback and usage
4. Keep phases high-level, refine when closer to implementation

### For Maintenance

1. Update this file when completing sprints
2. Move completed work to **Completed Sprints** section
3. Archive old documentation when no longer relevant
4. Keep **System Status** and **Key Metrics** current

---

**Document Owner**: Stefan Fries
**Last Review**: December 27, 2025
**Next Review**: January 2026

---

## Change Log

| Date | Change | Author |
| ------------ | ---------------------------------------------------------------- | ------------ |
| Dec 27, 2025 | Created master plan consolidating copilot-plan.md and ROADMAP.md | Stefan Fries |
| Dec 27, 2025 | Added Sprint 5 (Blob Storage) details | Stefan Fries |
| Jan 4, 2026 | Updated Sprint 7 status - OneDrive import + URL enrichment workflow | Stefan Fries |
