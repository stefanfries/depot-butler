# DepotButler Business Requirements

**Last Updated**: December 26, 2025
**Status**: Planning Phase

---

## Executive Summary

**Current State**: DepotButler successfully downloads and distributes Megatrend-Folger PDFs to subscribers via email and OneDrive upload.

**Target State**: Extend capabilities to extract Musterdepot (model portfolio) data from PDFs, build 15-year historical database, track portfolio changes automatically, and fetch intraday prices for performance analysis.

**Business Value**: Transform raw PDF publications into structured financial data enabling performance tracking, trend analysis, and data-driven investment decisions.

---

## Initial situation

I am the subscriber of the Megatrend-Folger publication which is issued on a
weekly basis. Each edition contains a table of a so-called "Musterdepot"
listing the details of up to approx. 25 Call Warrants:

- Unternehmen (underlying)
- WKN
- Stück / quantity
- Kaufdatum / buying date
- Kaufkurs / buying price
- Akt. Kurs
- Kurswert
- Performance. (in %)
- Anteil

Below the table the total value of all items as well as the Cash value in the
"Musterdepot" for the time of publication are given. Currently I have the
weekly publications of the last 15 years as pdf files.

## Business intention

From the weekly publications (the historical ones as well as the new ones
issued every week) I want to extract some of the details of the table (WKN,
underliying, Quantity, Kaufdatum, Kaufkurs) to track the performance of the
depot over time. Therefore, I want to build the entire history of the depot
in MongoDB.

If the composition of the depot has changed compared to last weeks edtion due
to any BUY oder SELL transactions, the depot history must be updated and a new
depot entry must be added with a "valid_from" date according to the date of
publication. If there is no change in the depot, only the "last_updated" value
of the last depot entry will be updated.

To also get the depot values between publishing dates I want to extract the
WKNs of the most recent depot. A separate job (running every weekday evening
after market close) should fetch the prices (for a time period and interval
provided) for every WKN in the list and save the data to the MongoDB. By these
means I am the able to track the performance of the entire depot as well as
the performace of every single WKN and use these data for further evaluation
and recommendations.

## Questions / advise needed

### 1. How to structure the code for the various jobs

**Status**: ✅ **RESOLVED** - See [ROADMAP.md](ROADMAP.md) Phase 1-2

**Implementation**:

- extract the Musterdepot table from the publication pdf and update MongoDB
  each time a new Megarend Folger publication has been processed
- extract all WKNs of the most recent depot for further processing by intrady
  price data fetcher
- fetch intraday price data from the web and store them to MongoDB

**Decision**: Service layer architecture with dedicated services:

- `pdf_extraction_service.py` - Parse PDF tables
- `depot_tracking_service.py` - Manage temporal portfolio history
- `price_fetcher_service.py` - Fetch and store intraday prices

See [ROADMAP.md](ROADMAP.md#service-layer-design) for details.

---

### 2. How to structure the workflow(s)?

**Status**: ✅ **RESOLVED** - See [architecture.md](architecture.md)

**Original question**:

- create one big workflow covering all steps needed?
- split the workflow into seperate logical parts to gain flexibility in
  composing individual workflows. These parts could be:

  - download (from the boersenmedien website)
  - distribute (via email and/or OneDrive upload)
  - extract Musterdepot table from pdf and update depot history
  - any post processing activites (like BUY/SELL recommendations based on
    specific evaluation)

**Decision**: Modular workflow with sequential phases:

1. Login → Discover subscriptions → Sync to MongoDB
2. Process each publication: Download → Extract → Distribute → Track
3. Separate scheduled job for intraday price fetching

Current implementation already supports modular design. PDF extraction and depot tracking will be added as new steps in the publication processing loop.

---

### 3. How to structure the Git repositories

**Status**: ✅ **RESOLVED** - See [ROADMAP.md](ROADMAP.md#repository-strategy-monorepo-)

**Original question**:

- backend and frontend components
- single repo vs multi repo
- and perhaps many more questions which will come up over time

Can you assist on these questions?

**Decision**: **Monorepo** - Keep all components in depot-butler

- Single developer workflow
- Shared types/models
- Atomic commits across stack
- Future dashboard: `frontend/` directory in same repo

---

### 4. How / where to store the publications

**Status**: ✅ **RESOLVED** - Azure Blob Storage Cool tier

**Current state**:

- currently publications are stored only temporarily on a file service in
  Azure and they are deleted (cleanup) after distribution
- would is probably better to store them permanenttly on Azure, e.g. for 1 or
  10 years (a single edition takes aproc 800 kB).
- what would this cost in Azure? Are there cost effictive options like using
  archive store or a hierarchical storage system?

**Analysis & Decision**:

**Storage Options Compared**:

- Azure Files (current temp): ~€0.06/GB/month = €0.024/month for 400MB
- Azure Blob Hot tier: ~€0.018/GB/month = €0.007/month
- Azure Blob Cool tier: ~€0.010/GB/month = €0.004/month ✅ **CHOSEN**
- Azure Blob Archive tier: ~€0.002/GB/month = €0.0008/month (after 1 year)

**Cost estimate (10 years)**:

- Total data: 52 weeks × 10 years × 0.8 MB = ~400 MB
- Cool tier (year 1): 0.4 GB × €0.01 × 12 months = €0.048
- Archive tier (years 2-10): 0.4 GB × €0.002 × 108 months = €0.086
- **Total 10-year cost: €0.13** (negligible)

**Decision**:

- Use **Azure Blob Storage Cool tier** for long-term PDF archive
- Keep **Azure Files** for temp processing (existing workflow, no disruption)
- Lifecycle policy: Move to Archive tier after 1 year (automatic)
- Container name: `editions` (matches domain language)
- Track archived PDFs in `processed_editions` collection with blob URLs
- Consistent filename pattern across all storage layers
- Bonus: Extract metadata (title, issue, date) from website during collection

**Implementation**: Phase 0 - Historical PDF Collection (see [ROADMAP.md](ROADMAP.md#phase-0-historical-pdf-collection--new))

---

## Acceptance Criteria

### Phase 1: PDF Extraction

- ✅ Extract all fields from Musterdepot table (WKN, underlying, quantity, dates, prices)
- ✅ Process 15 years of historical PDFs with <1% error rate
- ✅ Detect portfolio changes (BUY/SELL) automatically
- ✅ Store temporal history with proper versioning

### Phase 2: Intraday Prices

- ✅ Fetch hourly prices for all active warrants
- ✅ <5 minute data latency
- ✅ 90-day retention with automatic cleanup
- ✅ Handle API failures gracefully

### Phase 3: Dashboard

- ✅ Answer: "What was portfolio value on date X?"
- ✅ Show individual warrant performance over time
- ✅ Load time <2 seconds for 15 years of data

---

## Related Documentation

- **[ROADMAP.md](ROADMAP.md)** - Detailed implementation phases and timelines
  - **Phase 0 (NEW)**: Historical PDF collection and Azure storage
  - Updated schemas support multi-asset classes
  - Weekly snapshots regardless of composition changes
- **[architecture.md](architecture.md)** - Current system architecture
- **[CODE_QUALITY.md](CODE_QUALITY.md)** - Development standards and metrics

---

## Recent Decisions (December 26, 2025)

### 1. Multi-Asset Class Support ✅

**Decision**: Extend beyond warrants to support all major asset classes

**Asset Classes**:

- Stock (Aktie)
- Bond (Anleihe)
- ETF
- Fund (Fonds)
- Warrant (Optionsschein) - with subtype: call/put
- Certificate (Zertifikat) - with subtypes: discount/bonus/etc.
- Commodity (Rohstoff)
- Index
- Currency (Währung)

**Impact**: `Warrant` model renamed to `Instrument`, added `asset_class` and `subtype` fields

### 2. Weekly Snapshots ✅

**Decision**: Create depot snapshot every week, regardless of composition changes

**Rationale**: Track total portfolio value over time, even when holdings unchanged

**Impact**: Changed temporal logic from "snapshot on change" to "weekly snapshot always"

### 3. Transaction Tracking ✅

**Decision**: Support multiple transactions per week (BUY+SELL combinations)

**Impact**: `change_type` changed from single enum to `change_types: list[str]`

### 4. Azure PDF Storage ✅

**Decision**: Store historical PDFs in Azure Blob Storage (Cool tier)

**Benefits**:

- Avoid repeated downloads during development
- Fast iteration on PDF parsing
- Long-term publication archive
- Cost: ~€0.01/month for 400MB

**Impact**: New Phase 0 added to roadmap before PDF extraction development

---

**Document Owner**: Stefan Fries  
**Last Review**: December 26, 2025  
**Next Review**: After Phase 0 completion
