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

## Validation Checklist

### 1. Website Crawling (CRITICAL for Phase 0)

```powershell
uv run python scripts/validation/test_website_crawl.py
```

**Expected outcome**:

- ✅ Access boersenmedien.com ausgaben pages
- ✅ Parse edition metadata (title, issue, date)
- ✅ Discover 480+ available editions

**If it fails**:

- Check BOERSENMEDIEN_COOKIE in .env
- Inspect HTML structure (may need to adjust selectors)
- Verify website hasn't changed structure

---

### 2. PDF Parsing (CRITICAL for Phase 1)

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

### 3. Azure Blob Storage (CRITICAL for Phase 0)

```powershell
uv run python scripts/validation/test_blob_storage.py
```

**Expected outcome**:

- ✅ Connect to Azure Storage
- ✅ Create test container
- ✅ Upload/download/delete test blob

**If it fails**:

- Check AZURE_STORAGE_CONNECTION_STRING in .env
- Verify Azure Storage account exists
- Check network connectivity

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

## Validation Timeline

**TODAY (2 hours)**:

1. Run test_website_crawl.py (30 min)
2. Fix any HTML parsing issues (30 min)
3. Run test_blob_storage.py (30 min)
4. Review results and decide (30 min)

**TOMORROW (if validation passes)**:

- Start Phase 0 implementation
- Create edition_crawler.py service
- Create collect_historical_pdfs.py script

**IF VALIDATION FAILS**:

- Debug and iterate on failing tests
- Adjust Phase 0 plan if needed
- Estimate impact on timeline

---

## Getting Help

If validation fails:

1. Check logs in `logs/depotbutler.log`
2. Review error messages carefully
3. Test components individually
4. Ask for help with specific error details

---

**Last Updated**: December 26, 2025
