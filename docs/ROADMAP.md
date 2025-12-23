# DepotButler Feature Roadmap

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

**Purpose**: Track portfolio composition over time with temporal versioning

```javascript
{
  _id: ObjectId,
  valid_from: ISODate("2025-12-23"),      // Publication date
  valid_until: ISODate("2025-12-30") | null,  // null = current version
  publication_date: ISODate("2025-12-23"),
  publication_id: "megatrend-folger",
  warrants: [
    {
      wkn: "AB1234",
      underlying: "SAP SE",
      quantity: 100,
      purchase_date: ISODate("2024-06-15"),
      purchase_price: 150.50,
      current_price: 162.30,      // At publication time
      current_value: 16230.00,    // quantity * current_price
      performance_pct: 7.84
    }
  ],
  total_value: 125000.00,
  cash_value: 5000.00,
  total_depot_value: 130000.00,
  change_type: "BUY" | "SELL" | "NONE",   // Reason for new version
  changed_positions: ["AB1234", "CD5678"], // Which WKNs changed
  last_updated: ISODate("2025-12-23T10:00:00Z"),
  created_at: ISODate("2025-12-23T10:00:00Z")
}

// Indexes
{ valid_from: -1 }                    // Find by date
{ publication_id: 1, valid_from: -1 }  // Latest for publication
{ "warrants.wkn": 1 }                 // Find by warrant
```

**Temporal Logic**:

- When composition changes → Create new document, set previous `valid_until = new.valid_from`
- When no changes → Update only `last_updated` on current document
- Current snapshot: `valid_until = null`

### 2. `warrants` Collection - Master Data

**Purpose**: Reference data for all warrants ever seen

```javascript
{
  _id: "AB1234",  // WKN as primary key
  underlying: "SAP SE",
  isin: "DE0007164600",  // Optional: lookup via API
  type: "Call Warrant",
  first_seen: ISODate("2024-06-15"),
  last_seen: ISODate("2025-12-23"),
  active: true,  // Currently in portfolio
  total_appearances: 52,  // Number of weeks held
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

### Phase 1: PDF Extraction & Depot History Tracking ⏳

**Duration**: 2-3 weeks
**Goal**: Extract Musterdepot data from PDFs and build temporal database

#### Tasks

1. **Add PDF Extraction Service** (4 hours)
   - Install `pdfplumber`
   - Create `pdf_extraction_service.py`
   - Implement table parsing logic
   - Handle German date/number formats
   - Extract: WKN, underlying, quantity, purchase_date, purchase_price
   - Add error handling for malformed tables

2. **Create Domain Models** (2 hours)

   ```python
   class Warrant(BaseModel):
       wkn: str
       underlying: str
       quantity: int
       purchase_date: date
       purchase_price: Decimal
       current_price: Decimal | None = None

   class DepotSnapshot(BaseModel):
       publication_date: date
       publication_id: str
       warrants: list[Warrant]
       total_value: Decimal
       cash_value: Decimal
   ```

3. **Implement MongoDB Repositories** (6 hours)
   - `depot_repository.py` - CRUD for depot history
   - `warrant_repository.py` - Master data management
   - Add temporal query methods (get_at_date, get_current, get_changes)
   - Write repository tests

4. **Build Depot Tracking Service** (6 hours)
   - Create `depot_tracking_service.py`
   - Implement change detection logic (compare snapshots)
   - Handle BUY/SELL/NONE scenarios
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

**Total Estimated Time**: 32 hours (2-3 weeks at 50% capacity)

**Deliverables**:

- ✅ PDF extraction working for Megatrend-Folger
- ✅ 15 years of depot history in MongoDB
- ✅ Automated tracking for new publications
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

1. **PDF Access**: Where are the 15 years of historical PDFs stored? (OneDrive, local?)
2. **Table Format Consistency**: Do all historical PDFs have the same table structure?
3. **Pilot Scope**: Test with 1 year first, or full 15 years immediately?
4. **Data Validation**: Manual spot-checks needed after backfill?
5. **Price API**: Acceptable to use unofficial APIs (yfinance) or require paid/official?
6. **Dashboard Access**: Public or authentication required?

---

## References

- **Current Implementation**: [architecture.md](architecture.md)
- **Code Quality Standards**: [CODE_QUALITY.md](CODE_QUALITY.md)
- **Contributing Guide**: [CONTRIBUTING.md](CONTRIBUTING.md)
- **Sprint History**: Sprint 2-4 completed (Dec 21-23, 2025)

---

**Document Owner**: Stefan Fries
**Reviewers**: GitHub Copilot, Self
**Approval Date**: TBD
