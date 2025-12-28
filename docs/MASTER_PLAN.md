# DepotButler Master Implementation Plan

**Last Updated**: December 27, 2025
**Status**: Sprint 5 In Progress (Blob Storage Archival)

---

## Purpose

This document consolidates all past, current, and future implementation work for DepotButler into a single source of truth. It replaces the previous `copilot-plan.md` and `ROADMAP.md` files.

---

## Quick Navigation

- [✅ Completed Sprints](#completed-sprints-1-4) - Sprint 1-4 (Dec 2025)
- [🚧 Current Sprint](#current-sprint-5-blob-storage-archival) - Sprint 5 (Dec 27, 2025)
- [⏳ Near-Term Work](#near-term-sprints-6-9) - Sprints 6-9 (planned)
- [🔮 Future Vision](#future-vision-phases-1-4) - Long-term features
- [📊 System Status](#system-status-december-27-2025) - Current capabilities

---

## Completed Sprints (1-4)

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

## Current Sprint 5: Blob Storage Archival

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
- ✅ Phase 5.4: Testing & Validation (85%) - Verified integration, deferred full e2e testing

**Sprint 5 Achievements**:

1. **Azure Blob Storage Integration**: Complete archival pipeline from workflow to Azure Storage (Cool tier)
2. **Caching Layer**: `--use-cache` flag enables retrieval from blob storage instead of website downloads
3. **Granular Timestamps**: MongoDB tracks `downloaded_at`, `email_sent_at`, `onedrive_uploaded_at`, `archived_at`
4. **Non-Blocking Archival**: Blob storage failures don't impact email/OneDrive delivery
5. **Graceful Degradation**: Workflow continues if blob storage not configured
6. **Comprehensive Testing**: 271 unit tests (including 8 new blob archival tests)

**Deferred Work** (10%):
- Historical PDF collection script (`scripts/collect_historical_pdfs.py`) - 4-5 hours
- Full end-to-end testing with real archival (waiting for new editions)
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
2. ✅ Confirmed blob storage integration in workflow
3. ✅ Validated Azure Storage account setup (`depotbutlerarchive`)
4. ✅ Verified existing blob in storage (test PDF from Phase 5.1)
5. ✅ Confirmed `--use-cache` flag implementation
6. ⏳ **Deferred**: Historical script testing (script not yet built - Phase 5.3 Task 3)
7. ⏳ **Deferred**: Cost verification (requires >1 month of operation)

**Test Results**:

**Azure Storage Configuration**:
- ✅ Storage Account: `depotbutlerarchive` (Germany West Central, Cool tier)
- ✅ Container: `editions` (exists and accessible)
- ✅ Connection string configured in environment
- ✅ Blob service initializes successfully: `✓ Blob storage service initialized [container=editions]`

**Workflow Integration**:
- ✅ Blob service properly initialized in workflow
- ✅ Graceful degradation when blob service unavailable
- ✅ Non-blocking error handling (workflow continues on blob failures)

**Existing Blob Verification**:
```powershell
$ az storage blob list --container-name editions --account-name depotbutlerarchive
Name: 2025/test-publication/2025-12-27_Test-Publication_01-2025.pdf
Size: 50 bytes
LastModified: 2025-12-27T18:22:11+00:00
```

**Code Verification**:
- ✅ 271 unit tests passing (including 8 new blob archival tests)
- ✅ `_archive_to_blob_storage()` method implemented with non-blocking error handling
- ✅ `_download_edition()` checks cache when `use_cache=True`
- ✅ MongoDB metadata updates for blob URL, path, container, size

**Limitations**:
- ⚠️  Real-world archival testing limited (editions already processed)
- ⚠️  Cache hit scenario not fully tested (requires reprocessing or new edition)
- ⚠️  Historical collection script not yet built for bulk testing

**Success Criteria Met**:
- ✅ PDFs can be archived to Azure Blob Storage (confirmed via test blob)
- ✅ Blob storage properly integrated into workflow
- ✅ `--use-cache` flag implemented and ready to use
- ⏳ Full end-to-end testing deferred until new editions arrive
- ⏳ Cost verification deferred (requires operational data)

**Recommendations**:
1. Monitor blob storage costs over next 30 days
2. Test cache hit scenario when new edition arrives
3. Build historical collection script to populate archive with past editions
4. Consider forced reprocessing for comprehensive end-to-end testing

**Commits**: `0ceca80` (test suite + docs)

---

## Near-Term Sprints (6-9)

### Sprint 6: Publication Preference Management Tools ⏳

**Status**: PLANNED
**Priority**: Medium
**Estimated Duration**: 1 day

**Objectives**:

- Admin tools for managing recipient preferences
- Bulk preference updates
- Reporting on preference distribution

**Deliverables**:

1. [ ] `scripts/manage_recipient_preferences.py`
   - Add/remove publication preferences for recipient
   - List current preferences
   - Bulk updates (e.g., "add publication X to all recipients")
2. [ ] `scripts/check_recipients.py` enhancements
   - Show preference coverage statistics
   - List recipients without preferences
   - Per-publication recipient counts
3. [ ] Validation queries for preference health
4. [ ] Documentation for preference management

**Why Not Done Yet**: Current workflow functional without advanced preference management

---

### Sprint 7: Monitoring & Observability ⏳

**Status**: PLANNED
**Priority**: Medium
**Estimated Duration**: 2 days

**Objectives**:

- Better visibility into workflow execution
- Performance metrics
- Error tracking and alerting

**Deliverables**:

1. [ ] Structured logging with correlation IDs
2. [ ] Performance metrics collection
   - Publication processing time
   - API response times
   - Upload speeds
3. [ ] Error aggregation and reporting
4. [ ] Optional: Application Insights integration
5. [ ] Dashboard for key metrics (Streamlit or simple HTML)

---

### Sprint 8: Deployment & CI/CD Improvements ⏳

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

### Sprint 9: Documentation & Knowledge Base ⏳

**Status**: PLANNED
**Priority**: Medium
**Estimated Duration**: 1 day

**Objectives**:

- Consolidate documentation
- Create troubleshooting guides
- Document operational procedures

**Deliverables**:

1. [ ] Architecture diagrams (Mermaid)
2. [ ] Troubleshooting guide (common issues)
3. [ ] Operational runbook (what to do when...)
4. [ ] API documentation (if needed)
5. [ ] This master plan (keep updated!)

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

## System Status (December 27, 2025)

### ✅ Currently Working

**Core Features**:

- Multi-publication processing (all active publications in one run)
- Publication auto-discovery and sync from website
- Edition tracking (prevents duplicates per publication)
- Email distribution to recipients
- OneDrive upload with folder organization
- Chunked upload optimization (10MB chunks, 28x faster)
- Smart filename generation (title case, readable)
- Consolidated notifications (single summary email)
- Dry-run mode for safe testing
- MongoDB-driven configuration (dynamic)

**Infrastructure**:

- Azure Container Apps deployment
- Scheduled jobs (daily execution)
- MongoDB Atlas database
- Azure Blob Storage (archival - integration in progress)
- GitHub Actions CI/CD

**Test Coverage**:

- 241 tests passing
- 72% code coverage
- Integration tests for multi-publication scenarios

---

### 🚧 In Progress

**Sprint 5: Blob Storage Archival** (60% complete)

- ✅ BlobStorageService implementation
- ✅ Enhanced schema with granular timestamps
- 🚧 Workflow integration (next task)
- ⏳ Historical collection script
- ⏳ Testing and validation

---

### ❌ Not Yet Implemented

**Near-Term** (Sprints 6-9):

- Advanced recipient preference management tools
- Monitoring and observability enhancements
- Deployment automation improvements
- Consolidated documentation

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
