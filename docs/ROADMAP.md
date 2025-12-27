# DepotButler Feature Roadmap

> **⚠️ ARCHIVED**: This document has been consolidated into [MASTER_PLAN.md](MASTER_PLAN.md) as of December 27, 2025.  
> Content preserved for historical reference. See MASTER_PLAN.md for current roadmap.

**Last Updated**: December 23, 2025
**Status**: Planning Phase

---

## Vision

Expand DepotButler from a simple PDF distribution service into a comprehensive financial portfolio tracking and analysis system that:

1. Extracts Musterdepot (model portfolio) data from Megatrend-Folger publications
2. Tracks portfolio composition changes over time (15 years of historical data)
3. Fetches intraday price data for active warrants
4. Provides performance analytics and insights
5. Enables data-driven investment recommendations

---

## Business Objective

### Current Capability

DepotButler automatically downloads and distributes Megatrend-Folger PDFs to subscribers via email and OneDrive.

### Target Capability

Extract structured data from publications to build a temporal database of portfolio history, enabling:

- Historical performance analysis across 15 years
- Intraday tracking of current positions
- Change detection (BUY/SELL transactions)
- Performance metrics per warrant and overall portfolio
- Future: ML-based recommendations

---

## Architecture Decisions

### Repository Strategy: **Monorepo** ✅

**Decision**: Keep all components in the existing depot-butler repository

**Rationale**:

- Single developer workflow
- Shared types/models between backend and frontend
- Atomic commits across stack
- Single CI/CD pipeline
- Existing structure already supports extensions

**Structure**:

```text
depot-butler/
  ├── src/depotbutler/          # Python backend (existing)
  ├── frontend/                 # Future: Dashboard (Phase 3)
  ├── docs/                     # Documentation (existing)
  ├── scripts/                  # Utility scripts (existing)
  └── tests/                    # Test suite (existing)
```

### Service Layer Design

**Pattern**: Extend existing Clean Architecture with service layer separation

```text
Domain Layer (models.py)
  ├── Edition, Subscription, UploadResult (existing)
  ├── Warrant (new)
  ├── DepotSnapshot (new)
  └── PriceData (new)

Infrastructure Layer
  ├── httpx_client.py (existing)
  ├── db/repositories/
  │   ├── depot.py (new)
  │   ├── warrant.py (new)
  │   └── price_data.py (new)

Application Layer (services/)
  ├── pdf_extraction_service.py (new)
  ├── depot_tracking_service.py (new)
  ├── price_fetcher_service.py (new)
  └── publication_processing_service.py (extend)
```

---

## MongoDB Schema Design

### 1. `depots` Collection - Temporal Portfolio History

**Purpose**: Track portfolio composition over time with weekly snapshots

```javascript
{
  _id: ObjectId,
  valid_from: ISODate("2025-12-23"),      // Publication date
  valid_until: ISODate("2025-12-30"),     // Next publication date (null = current)
  publication_date: ISODate("2025-12-23"),
  publication_id: "megatrend-folger",
  instruments: [                           // Renamed from "warrants" for flexibility
    {
      wkn: "AB1234" | null,               // Not all assets have WKN
      isin: "DE0007164600" | null,        // International identifier
      ticker: "SAP" | null,               // Stock ticker symbol
      name: "SAP SE Call Warrant",        // Human-readable name
      asset_class: "warrant",             // stock|bond|etf|fund|warrant|certificate|commodity|index|currency
      subtype: "call" | null,             // call/put for warrants, etc.
      underlying: "SAP SE" | null,        // For derivatives only
      quantity: 100,
      purchase_date: ISODate("2024-06-15"),
      purchase_price: 150.50,
      current_price: 162.30,              // At publication time
      current_value: 16230.00,            // quantity * current_price
      performance_pct: 7.84
    }
  ],
  total_value: 125000.00,
  cash_value: 5000.00,
  total_depot_value: 130000.00,
  composition_changed: true,                        // NEW: Flag for composition changes
  change_types: ["BUY", "SELL"],                   // List of change types (empty if none)
  changed_instruments: ["AB1234", "CD5678"],       // Which instruments changed
  transactions_summary: {                           // Optional: Summary of changes
    buys: 2,
    sells: 1,
    total_changes: 3
  },
  last_updated: ISODate("2025-12-23T10:00:00Z"),
  created_at: ISODate("2025-12-23T10:00:00Z")
}

// Indexes
{ valid_from: -1 }                          // Find by date
{ publication_id: 1, valid_from: -1 }        // Latest for publication
{ "instruments.wkn": 1 }                     // Find by WKN
{ "instruments.isin": 1 }                    // Find by ISIN
{ "instruments.asset_class": 1 }             // Filter by asset class
```

**Temporal Logic** (Updated):

- **Every publication creates a new snapshot** (weekly, regardless of changes)
- Set previous snapshot's `valid_until = new.valid_from`
- `composition_changed` flag indicates if holdings changed
- `change_types` list tracks what happened (empty array = no changes, just price updates)
- Current snapshot: `valid_until = null`

**Benefits**:
- Time-series performance tracking works seamlessly
- No need to interpolate missing weeks
- Query "depot on date X" returns exact snapshot
- Disk space negligible (~5KB × 52 weeks = 260KB/year)

### 2. `instruments` Collection - Master Data

**Purpose**: Reference data for all instruments (stocks, warrants, ETFs, etc.) ever seen

```javascript
{
  _id: ObjectId,                            // Generated ID
  wkn: "AB1234" | null,                     // German WKN (not unique across asset classes)
  isin: "DE0007164600" | null,              // International identifier (preferred unique key)
  ticker: "SAP" | null,                     // Stock ticker
  name: "SAP SE Call Warrant",             // Human-readable name
  asset_class: "warrant",                  // stock|bond|etf|fund|warrant|certificate|commodity|index|currency
  subtype: "call" | null,                   // Asset-specific subtype
  underlying: "SAP SE" | null,             // For derivatives
  first_seen: ISODate("2024-06-15"),
  last_seen: ISODate("2025-12-23"),
  active: true,                             // Currently in portfolio
  total_appearances: 52,                    // Number of weeks held
  metadata: {
    strike_price: 100.00,
    expiry_date: ISODate("2026-12-31"),
    issuer: "Deutsche Bank"
  }
}

// Indexes
{ underlying: 1 }
{ active: 1 }
{ last_seen: -1 }
```

### 3. `intraday_prices` Collection - Time Series Data

**Purpose**: Store intraday price movements for active warrants

```javascript
{
  _id: ObjectId,
  wkn: "AB1234",
  timestamp: ISODate("2025-12-23T14:00:00Z"),
  price: 162.30,
  volume: 1500,
  bid: 162.20,
  ask: 162.40,
  source: "yahoo_finance",
  fetched_at: ISODate("2025-12-23T14:05:00Z")
}

// Indexes (Time Series Optimized)
{ wkn: 1, timestamp: -1 }  // Query by WKN + date range
{ timestamp: -1 }           // Cleanup old data
```

**Data Retention**: Keep intraday data for 90 days (configurable)

---

## Technology Stack

### Phase 1: PDF Extraction

- **pdfplumber** `0.11.4` - Table extraction from PDFs (best for structured tables)
- **pandas** `2.2.0` - Data manipulation and validation (optional)
- **Alternative**: `camelot-py` if table detection proves difficult

### Phase 2: Price Data APIs

- **Primary**: `yfinance` - Free, works for German warrants, no API key needed
- **Backup**: Alpha Vantage (25 calls/day free tier)
- **WKN Mapping**: OpenFIGI API (WKN → ISIN → ticker symbol)

### Phase 3: Dashboard (Future)

**Option A - Quick Start**: Streamlit

- Python-only, no JavaScript required
- Rapid prototyping
- Built-in chart components
- Ideal for data scientists

**Option B - Production**: React + FastAPI

- Separate frontend/backend
- Professional user experience
- Better scalability
- Reusable REST API

**Recommendation**: Start with Streamlit, migrate to React if needed

### Phase 4: Analytics

- **Plotly** - Interactive charts
- **NumPy/Pandas** - Statistical calculations
- **scikit-learn** - ML-based predictions (future)

---

## Implementation Phases

### Phase 0: Historical PDF Collection 📦 **NEW**

**Duration**: 1-2 days
**Goal**: Collect historical PDFs with metadata from website, store in Azure Blob Storage (Cool tier) for development and long-term retention

**Why this phase is critical**:

- Avoid repeated downloads from boersenmedien.com during development
- Enable offline development and fast iteration
- Prevent IP blocking from excessive requests
- Capture metadata (issue numbers, titles, publication dates) automatically from website
- Answer original requirement: long-term publication storage
- Cost: ~€0.004/month for 400MB in Azure Blob Cool tier (6x cheaper than Azure Files)

#### Tasks

1. **Setup Azure Blob Storage** (1 hour)
   - Create container: `editions` (or `edition-archive`)
   - Configure Cool tier for cost optimization (~€0.01/GB/month)
   - Set lifecycle policy: move to Archive tier after 1 year (€0.002/GB/month)
   - Use managed identity for authentication (recommended) or connection string

2. **Create Website Edition Crawler** (3 hours)

   ```python
   # New: services/edition_crawler.py
   class WebsiteEditionCrawler:
       """Discover editions from boersenmedien website with metadata"""
       
       async def discover_all_editions(self, subscription_id: str) -> list[EditionMetadata]:
           """Paginate through ausgaben pages (16 pages × 30 editions)"""
           # URL: https://konto.boersenmedien.com/produkte/abonnements/2477462/AM-01029205/ausgaben?page={n}
           # Extract: Title, Issue (21/2025), Erscheinungsdatum, Download URL
           
       async def download_edition_from_url(self, url: str) -> bytes:
           """Download PDF from discovered download URL"""
   ```

3. **Create Collection Script** (4 hours)

   ```python
   # scripts/collect_historical_pdfs.py
   async def collect_from_website():
       """Primary: Crawl website, download with metadata"""
       # 1. Discover all editions (480+ editions)
       # 2. Check processed_editions for existing
       # 3. Download missing editions in batches
       # 4. Archive to Blob Storage with consistent naming
       # 5. Save metadata to processed_editions collection
       
   async def supplement_from_onedrive():
       """Fallback: Older editions from OneDrive (no metadata)"""
       # For very old editions not on website
       # Download from OneDrive, archive to Blob
   ```

4. **Extend Storage Service** (3 hours)
   - Add `BlobStorageService` class (azure-storage-blob SDK)
   - Methods: `store_pdf()`, `get_cached_pdf()`, `list_editions()`, `exists()`
   - Use existing filename pattern: `{date}_{Title-Cased}_{issue}.pdf`
   - Example: `2025-12-18_Megatrend-Folger_51-2025.pdf` (EXISTING convention)
   - Blob path structure: `{year}/{publication_id}/{filename}`
   - Fallback to local filesystem if Azure unavailable

5. **Enhance processed_editions Collection** (2 hours)

   ```javascript
   // Enhanced with granular pipeline tracking
   {
     _id: "2025-12-23_megatrend-folger",
     publication_id: "megatrend-folger",
     date: ISODate("2025-12-23"),
     
     // Metadata from website
     issue_number: "51/2025",              // Separate field for queries (also in filename)
     title: "Megatrend Folger 51/2025",
     publication_date: ISODate("2025-12-23"),
     
     // Download tracking
     download_url: "https://konto.boersenmedien.com/.../download",  // Keep original URL
     downloaded_at: ISODate("2025-12-23T10:00:00Z"),
     
     // Archive tracking
     blob_url: "https://account.blob.core.windows.net/editions/2025/megatrend-folger/2025-12-23_Megatrend-Folger_51-2025.pdf",
     blob_path: "2025/megatrend-folger/2025-12-23_Megatrend-Folger_51-2025.pdf",
     blob_container: "editions",
     archived_at: ISODate("2025-12-23T10:01:00Z"),
     file_size_bytes: 819200,
     
     // Distribution tracking (granular)
     distributed_at: ISODate("2025-12-23T10:02:00Z") | null,
     email_sent_at: ISODate("2025-12-23T10:02:30Z") | null,
     onedrive_uploaded_at: ISODate("2025-12-23T10:03:00Z") | null,
     
     // Extraction tracking (Phase 1 - future)
     extracted_at: ISODate("2025-12-23T10:04:00Z") | null,
     
     source: "website" | "onedrive"
   }
   ```
   
   **Rationale for granular timestamps**:
   - Track performance bottlenecks at each pipeline stage
   - Enable targeted retry logic (e.g., retry distribution without re-download)
   - Audit trail for troubleshooting
   - Metrics dashboard (average times, success rates per stage)
   - Keep `download_url` for re-download capability if needed

6. **Update Workflow Integration** (2 hours)
   - Check Blob Storage cache before downloading from website
   - Archive new publications automatically after processing
   - Update tracking: set `archived_at`, `distributed_at`, `email_sent_at`, `onedrive_uploaded_at`
   - Add `--use-cache` flag for development mode
   - Configuration: `CLEANUP_ENABLED=False` for dev
   - Keep Azure Files for temp processing, Blob for archive

**Deliverables**:

- ✅ 480+ editions stored in Azure Blob Storage Cool tier (~400MB)
- ✅ Metadata captured (titles, issues, dates) from website
- ✅ Fast local iteration (no re-downloads during development)
- ✅ Long-term publication archive with lifecycle management
- ✅ Configurable cleanup suspension for development
- ✅ Existing filename pattern preserved: `YYYY-MM-DD_Title-Cased_XX-YYYY.pdf`
- ✅ Single source of truth: `processed_editions` collection with granular pipeline tracking
- ✅ Performance monitoring enabled via stage-specific timestamps

**Total Estimated Time**: 15 hours (2 days)

**Storage Architecture**:

- **Azure Files**: Temp processing (existing, keep for compatibility)
- **Blob Storage Cool tier**: Long-term archive (new, 6x cheaper than Files)
- **Blob Storage Archive tier**: Move after 1 year (lifecycle policy, 30x cheaper)

**Filename Convention** (EXISTING, do not change):

```text
Format: {date}_{Title-Cased}_{issue}.pdf
Example: 2025-12-18_Megatrend-Folger_51-2025.pdf

Components:
- date: YYYY-MM-DD (ISO format, sortable)
- title: Title-Cased with hyphens (e.g., "Megatrend-Folger")
- issue: XX-YYYY (slash→hyphen for filesystem compatibility)
```

---

### Phase 1: PDF Extraction & Depot History Tracking ⏳

**Duration**: 2-3 weeks
**Goal**: Extract Musterdepot data from PDFs and build temporal database with multi-asset support

#### Tasks

1. **Add PDF Extraction Service** (4 hours)
   - Install `pdfplumber`
   - Create `pdf_extraction_service.py`
   - Implement table parsing logic
   - Handle German date/number formats
   - Extract: WKN/ISIN, name, asset_class, subtype, quantity, dates, prices
   - Add error handling for malformed tables

2. **Create Domain Models** (3 hours)

   ```python
   class AssetClass(str, Enum):
       STOCK = "stock"              # Aktie
       BOND = "bond"                # Anleihe
       ETF = "etf"                  # ETF
       FUND = "fund"                # Fonds
       WARRANT = "warrant"          # Optionsschein
       CERTIFICATE = "certificate"  # Zertifikat
       COMMODITY = "commodity"      # Rohstoff
       INDEX = "index"              # Index
       CURRENCY = "currency"        # Währung

   class Instrument(BaseModel):     # Renamed from Warrant
       wkn: str | None = None
       isin: str | None = None
       ticker: str | None = None
       name: str
       asset_class: AssetClass
       subtype: str | None = None   # "call", "put", etc.
       underlying: str | None = None
       quantity: int
       purchase_date: date
       purchase_price: Decimal
       current_price: Decimal | None = None

   class DepotSnapshot(BaseModel):
       publication_date: date
       publication_id: str
       instruments: list[Instrument]  # Renamed from warrants
       total_value: Decimal
       cash_value: Decimal
       composition_changed: bool      # NEW
       change_types: list[str]        # NEW: ["BUY", "SELL"] or []
   ```

3. **Implement MongoDB Repositories** (6 hours)
   - `depot_repository.py` - CRUD for depot history with weekly snapshots
   - `instrument_repository.py` - Master data for all asset classes
   - Add temporal query methods (get_at_date, get_current, get_changes)
   - Write repository tests

4. **Build Depot Tracking Service** (7 hours)
   - Create `depot_tracking_service.py`
   - **Always create weekly snapshot** (composition changed or not)
   - Implement change detection logic (compare instruments)
   - Track multiple changes per week (BUY+SELL combinations)
   - Update `valid_until` on previous snapshots
   - Add comprehensive logging

5. **Integrate with Publication Workflow** (4 hours)
   - Extend `publication_processing_service.py`
   - Hook PDF extraction after download
   - Trigger depot tracking
   - Add dry-run support
   - Update tests

6. **Create Backfill Script** (4 hours)
   - `scripts/backfill_historical_pdfs.py`
   - Process 15 years of historical PDFs
   - Batch processing with progress tracking
   - Resume capability if interrupted
   - Validation and error reporting

7. **Testing** (6 hours)
   - Unit tests for PDF parsing (mock PDFs)
   - Integration tests for depot tracking
   - Test temporal queries
   - Test change detection scenarios
   - Validate against sample PDFs

**Total Estimated Time**: 36 hours (2-3 weeks at 50% capacity)

**Deliverables**:

- ✅ PDF extraction working for Megatrend-Folger (all asset classes)
- ✅ 15 years of depot history in MongoDB (weekly snapshots)
- ✅ Automated weekly tracking for new publications
- ✅ Multi-asset class support (warrants, stocks, ETFs, etc.)
- ✅ Composition change detection with transaction tracking
- ✅ Test coverage >80%

---

### Phase 2: Intraday Price Fetcher ⏳

**Duration**: 1 week
**Goal**: Fetch and store hourly price data for active warrants

#### Tasks

1. **Choose & Test Price API** (2 hours)
   - Test `yfinance` with German warrants
   - Verify data quality and latency
   - Implement WKN → ticker mapping (if needed)
   - Handle rate limits

2. **Create Price Data Models** (1 hour)

   ```python
   class PriceData(BaseModel):
       wkn: str
       timestamp: datetime
       price: Decimal
       volume: int | None = None
       source: str
   ```

3. **Implement Price Repository** (3 hours)
   - `price_data_repository.py`
   - Bulk insert operations
   - Time-series queries (get_range, get_latest)
   - Data cleanup (retention policy)

4. **Build Price Fetcher Service** (4 hours)
   - Create `price_fetcher_service.py`
   - Fetch prices for list of WKNs
   - Handle API errors and retries
   - Batch requests to respect rate limits
   - Log fetching statistics

5. **Create Scheduled Job Script** (3 hours)
   - `scripts/fetch_intraday_prices.py`
   - Get active WKNs from latest depot
   - Fetch hourly prices (runs every hour on weekdays)
   - Store to MongoDB
   - Error notifications

6. **Azure Container Apps Configuration** (2 hours)
   - Add new scheduled job
   - Configure cron: `0 9-17 * * 1-5` (hourly, 9am-5pm, weekdays)
   - Set environment variables
   - Test deployment

7. **Testing** (3 hours)
   - Mock API responses
   - Test bulk operations
   - Validate time-series queries
   - Test scheduled job logic

**Total Estimated Time**: 18 hours (1 week at 50% capacity)

**Deliverables**:

- ✅ Intraday prices fetched hourly
- ✅ 90-day historical price data
- ✅ Automated scheduled job in Azure
- ✅ Error monitoring and alerts

---

### Phase 3: Basic Analytics Dashboard ⏳

**Duration**: 2-3 weeks
**Goal**: Visualize depot history and performance

#### Tasks

1. **Setup Streamlit App** (2 hours)
   - Install Streamlit
   - Create `frontend/app.py`
   - Configure MongoDB connection
   - Setup routing/pages

2. **Depot Composition View** (6 hours)
   - Show current depot holdings
   - Historical composition (timeline slider)
   - Warrant details table
   - Buy/Sell transaction log

3. **Performance Charts** (8 hours)
   - Total depot value over time (line chart)
   - Individual warrant performance
   - Comparison: portfolio vs. DAX
   - Win/loss distribution

4. **WKN Deep Dive** (4 hours)
   - Select warrant for analysis
   - Price chart with buy/sell markers
   - Performance metrics (ROI, Sharpe ratio)
   - Intraday price movements

5. **Filters & Date Range Selection** (3 hours)
   - Date range picker
   - Filter by underlying
   - Filter by performance (top/bottom N)
   - Export to CSV

6. **Deployment** (3 hours)
   - Containerize Streamlit app
   - Deploy to Azure Container Apps
   - Configure authentication (optional)
   - Setup custom domain

7. **Testing & Polish** (4 hours)
   - User testing
   - Performance optimization
   - Mobile responsiveness
   - Documentation

**Total Estimated Time**: 30 hours (2-3 weeks)

**Deliverables**:

- ✅ Web dashboard accessible via browser
- ✅ Interactive charts and filters
- ✅ Historical analysis capabilities
- ✅ Deployed to Azure
- ✅ Deployed to Azure

---

### Phase 4: Advanced Analytics 📋 (Future)

**Duration**: Ongoing
**Goal**: ML-based insights and recommendations

#### Potential Features

1. **Performance Metrics**
   - Sharpe ratio, max drawdown, volatility
   - Correlation analysis with indices
   - Risk-adjusted returns

2. **Portfolio Optimization**
   - Suggest position sizing
   - Diversification recommendations
   - Rebalancing alerts

3. **Predictive Analytics**
   - Price trend forecasting (LSTM, Prophet)
   - Anomaly detection (unusual movements)
   - Pattern recognition (support/resistance)

4. **Smart Alerts**
   - Email/SMS on significant moves
   - Stop-loss breach warnings
   - Profit-taking opportunities

5. **Backtesting Engine**
   - Test strategies on historical data
   - Compare "what-if" scenarios
   - Performance attribution

**Estimated Time**: 40-60 hours (ongoing development)

---

## Technical Considerations

### PDF Parsing Challenges

**Expected Issues**:

- Table format changes between years
- OCR quality for scanned PDFs
- Multi-page tables
- German number formats (comma vs. period)

**Mitigation**:

- Manual verification for first backfill
- Configurable parsing rules per year/format
- Fallback to manual entry for problematic PDFs
- Store raw table data alongside parsed data

### API Rate Limits

**yfinance**: ~2000 requests/hour (unofficial)
**Strategy**:

- Fetch 25 WKNs hourly = well below limit
- Implement exponential backoff
- Cache responses (15-minute TTL)
- Fallback to cached data on errors

### Data Quality

**Validation Rules**:

- WKN format: 6 alphanumeric characters
- Prices must be positive
- Quantities must be positive integers
- Purchase dates must be <= publication date
- Detect and flag outliers (>100% single-day moves)

### Scalability

**Current Scale**:

- ~25 warrants per depot
- 52 snapshots/year
- ~2,000 price points/day (25 WKNs × hourly × 8 trading hours)

**Storage Estimate (1 year)**:

- Depot snapshots: ~5 KB × 52 = 260 KB
- Intraday prices: ~200 bytes × 2,000 × 250 days = 100 MB
- **Total**: ~100 MB/year (negligible for MongoDB)

**Performance**: No concerns until 100K+ warrants or 10M+ price points

---

## Risk Assessment

### High Risk

- **PDF format changes**: Megatrend-Folger changes table layout
  - *Mitigation*: Version-based parsers, manual fallback

- **API reliability**: yfinance unofficial, could break
  - *Mitigation*: Multiple API providers, graceful degradation

### Medium Risk

- **Historical data quality**: 15-year-old PDFs may have OCR issues
  - *Mitigation*: Manual review phase, spot checks

- **WKN → Ticker mapping**: Not all warrants have public tickers
  - *Mitigation*: Focus on underlying stock prices as proxy

### Low Risk

- **MongoDB storage limits**: Azure free tier has limits
  - *Mitigation*: Move to paid tier (~€25/month for 10GB)

---

## Success Metrics

### Phase 1

- ✅ 100% of historical PDFs processed successfully
- ✅ Change detection accuracy >95%
- ✅ Zero data loss during migration
- ✅ Processing time <2 seconds per PDF

### Phase 2

- ✅ Intraday prices fetched with <1% failure rate
- ✅ API response time <2 seconds per WKN
- ✅ Data latency <5 minutes

### Phase 3

- ✅ Dashboard loads in <2 seconds
- ✅ User can answer: "What was my portfolio value on date X?"
- ✅ Charts render smoothly for 15 years of data

---

## Dependencies & Prerequisites

### New Python Packages

```toml
# Add to pyproject.toml
[project]
dependencies = [
    # ... existing ...
    "pdfplumber>=0.11.4",      # Phase 1
    "yfinance>=0.2.50",        # Phase 2
    "pandas>=2.2.0",           # Phase 1 (optional)
    "streamlit>=1.40.0",       # Phase 3
    "plotly>=5.24.0",          # Phase 3
]
```

### Azure Resources

- MongoDB database (existing, increase storage if needed)
- Container Apps scheduled jobs (2 new jobs: backfill, intraday-fetch)
- Optional: Application Insights for dashboard monitoring

### Skills Required

- PDF parsing (learn: pdfplumber API)
- Temporal database patterns (learn: versioning strategies)
- Time-series data (learn: MongoDB time-series collections)
- Financial APIs (learn: yfinance, Alpha Vantage)
- Streamlit basics (learn: 2-hour tutorial)

---

## Next Steps

### Immediate (This Week)

1. ✅ Review and approve roadmap
2. Create GitHub issues/project board for tracking
3. Test PDF parsing on 2-3 sample Megatrend-Folger PDFs
4. Validate MongoDB schema design

### Short Term (Next 2 Weeks)

1. Implement Phase 1, Task 1-2 (PDF extraction + models)
2. Test parsing on 10 historical PDFs
3. Review results and adjust parsing logic
4. Decide on proceed/pivot

### Medium Term (January 2025)

1. Complete Phase 1 (backfill historical data)
2. Begin Phase 2 (intraday prices)
3. Test end-to-end workflow

### Long Term (Q1 2025)

1. Launch Phase 3 dashboard
2. Gather feedback from users (yourself!)
3. Plan Phase 4 features based on actual usage

---

## Questions to Resolve Before Starting

**Note**: Most questions originally raised in [BUSINESS_REQUIREMENTS.md](BUSINESS_REQUIREMENTS.md) have been resolved. Remaining open items:

1. **PDF Access**: Where are the 15 years of historical PDFs stored? (OneDrive, local?)
2. **Table Format Consistency**: Do all historical PDFs have the same table structure?
3. **Pilot Scope**: Test with 1 year first, or full 15 years immediately?
4. **Data Validation**: Manual spot-checks needed after backfill?
5. **Price API**: Acceptable to use unofficial APIs (yfinance) or require paid/official?
6. **Dashboard Access**: Public or authentication required?

---

## References

- **Business Requirements**: [BUSINESS_REQUIREMENTS.md](BUSINESS_REQUIREMENTS.md)
- **Current Implementation**: [architecture.md](architecture.md)
- **Code Quality Standards**: [CODE_QUALITY.md](CODE_QUALITY.md)
- **Contributing Guide**: [CONTRIBUTING.md](CONTRIBUTING.md)
- **Sprint History**: Sprint 2-4 completed (Dec 21-23, 2025)

---

**Document Owner**: Stefan Fries
**Reviewers**: GitHub Copilot, Self
**Approval Date**: TBD
