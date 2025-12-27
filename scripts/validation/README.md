# Validation Scripts

These scripts validate key assumptions before starting Phase 0 implementation.

## Prerequisites

```powershell
# Install dependencies
uv sync

# Configure environment
# Copy .env.example to .env and fill in:
# - BOERSENMEDIEN_COOKIE (for website access)
# - AZURE_STORAGE_CONNECTION_STRING (for blob storage)
```

## ✅ Validation Complete - Phase 0 Foundation Ready

**Status as of December 27, 2025**: All Phase 0 prerequisites validated and implemented!

### Phase 0 Foundation Components

✅ **BlobStorageService** - Azure Blob Storage integration complete
✅ **Enhanced Schema** - Granular timestamp tracking implemented  
✅ **Settings Integration** - Pydantic config for blob storage
✅ **Test Coverage** - All components tested and verified

**Next**: Workflow integration and historical PDF collection

---

## Validation Checklist

### 1. Website Crawling ✅ VALIDATED

```powershell
uv run python scripts/validation/test_website_crawl.py
```

**Status**: ✅ **PASS** - Authentication and website access working

---

### 2. PDF Parsing (For Phase 1)

```powershell
# Place 3-5 sample PDFs in data/tmp/
uv run python scripts/validation/test_pdf_parsing.py
```

**Expected outcome**:

- ✅ Extract tables from PDFs using pdfplumber
- ✅ Identify Musterdepot table structure
- ✅ Parse German number formats

**If it fails**:

- Test with PDFs from different years
- May need version-based parsers for format changes
- Consider alternative: camelot-py

---

### 3. Azure Blob Storage ✅ IMPLEMENTED

```powershell
uv run python scripts/validation/test_blob_storage.py
# Or test the service directly:
uv run python scripts/test_blob_service.py
```

**Status**: ✅ **COMPLETE**

- ✅ Azure Storage account `depotbutlerarchive` created
- ✅ BlobStorageService implemented and tested
- ✅ Settings integration via Pydantic (AZURE_STORAGE_*)
- ✅ Container "editions" ready for use
- ✅ All CRUD operations validated

---

### 4. yfinance (Optional - Phase 2 only)

```powershell
uv run python scripts/validation/test_yfinance.py
```

**Expected outcome**:

- ✅ Fetch prices for German stocks
- ⚠️ Warrants likely unavailable (expected)

**Notes**:

- This is for Phase 2 (intraday prices)
- Can be deferred until Phase 1 complete
- Warrant prices may require alternative APIs

---

## Decision Matrix

| Test | Result | Action |
|------|--------|--------|
| Website crawling | ✅ Pass | → Proceed to Phase 0 |
| Website crawling | ❌ Fail | → Debug HTML parsing, may need alternative approach |
| PDF parsing | ✅ Pass | → Proceed to Phase 1 (after Phase 0) |
| PDF parsing | ❌ Fail | → Test multiple PDFs, consider alternative parsers |
| Blob storage | ✅ Pass | → Proceed to Phase 0 |
| Blob storage | ❌ Fail | → Fix Azure credentials, verify account |
| yfinance | ✅/⚠️ Any | → Phase 2 can proceed (defer decision) |

---

## Phase 0 Progress

**✅ COMPLETED (December 27, 2025)**:

1. ✅ Azure Storage validation and setup
2. ✅ BlobStorageService implementation
3. ✅ Enhanced processed_editions schema with granular timestamps
4. ✅ Pydantic settings integration
5. ✅ Test coverage for all components

**🚧 IN PROGRESS**:

- Workflow integration (blob archival after distribution)
- Historical PDF collection script
- End-to-end testing

**📋 REMAINING**:

- Complete workflow integration
- Create `collect_historical_pdfs.py` script
- Test with real editions
- Backfill historical PDFs

---

## Getting Help

If validation fails:

1. Check logs in `logs/depotbutler.log`
2. Review error messages carefully
3. Test components individually
4. Ask for help with specific error details

---

**Last Updated**: December 27, 2025
**Phase 0 Status**: Foundation Complete - Ready for Workflow Integration
