# Validation Setup Guide

> **📦 ARCHIVED DOCUMENT**
> **Original Date**: December 26, 2025
> **Archived**: December 30, 2025
> **Status**: Historical reference only - validation phase complete
>
> This document was created for pre-implementation validation of Phase 0 (Azure Blob Storage integration).
> All objectives have been completed through Sprint 5-7 (December 2025).
>
> **See current status**: [MASTER_PLAN.md](../MASTER_PLAN.md)
> **Sprint completion**: Sprint 5 (Blob Storage), Sprint 7 (Historical Collection)

---

This guide helps you set up all prerequisites for running validation tests before Phase 0 implementation.

## Quick Start

```powershell
# Run automated setup helper
uv run python scripts/validation/setup_prerequisites.py
```

This script will:

1. ✅ Retrieve authentication cookie from MongoDB
2. ⚠️ Check Azure Storage configuration
3. ⚠️ Check for sample PDFs

---

## Manual Setup Steps

If you prefer manual setup or if the automated script fails:

### 1. Authentication Cookie (CRITICAL)

**Option A - Retrieve from MongoDB (Recommended):**

```powershell
# The setup script does this automatically
uv run python scripts/validation/setup_prerequisites.py
```

**Option B - Get manually:**

```powershell
# Connect to MongoDB and get cookie
mongosh "mongodb+srv://your-connection-string"
use depotbutler
db.config.findOne({_id: "auth"})
```

Then add to `.env`:

```env
BOERSENMEDIEN_COOKIE="bmag_session=your-cookie-value-here"
```

**Update cookie if expired:**

```powershell
python scripts/update_cookie_mongodb.py
```

---

### 2. Azure Storage Account (CRITICAL for Phase 0)

#### A. Create Storage Account

1. **Go to Azure Portal**: <https://portal.azure.com>
2. **Create Resource** → Search for "Storage Account"
3. **Configure**:
   - **Subscription**: Your subscription
   - **Resource Group**: `depot-butler` (or existing)
   - **Storage Account Name**: `depotbutler<unique>` (e.g., `depotbutler2025`)
   - **Region**: West Europe (or closest to you)
   - **Performance**: Standard
   - **Redundancy**: LRS (Locally Redundant Storage - cheapest)
4. **Networking**: Default (Public endpoint)
5. **Data Protection**: Default
6. **Review + Create**

**Cost**: ~€0.02/GB/month (Standard LRS) + €0.01/GB/month (Cool tier)

#### B. Get Connection String

1. Navigate to your storage account
2. **Settings** → **Access Keys**
3. Click **Show** next to Key1
4. **Copy** the "Connection string"

#### C. Add to Environment

Add to `.env` file:

```env
AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=depotbutler2025;AccountKey=your-key-here;EndpointSuffix=core.windows.net"
```

⚠️ **Important**: Keep this secret! Don't commit to Git.

---

### 3. Sample PDFs for Testing (Optional for now)

You need 2-3 sample PDFs to validate extraction works across different years.

#### Option A - Download from Website

1. Log in: <https://konto.boersenmedien.com>
2. Navigate to **Megatrend-Folger** → **Ausgaben**
3. Download 2-3 PDFs:
   - Recent (2025) - Latest issue
   - Mid-range (2020) - Test format consistency
   - Old (2015) - Test historical format
4. Save to: `data/tmp/`

#### Option B - Copy from OneDrive (if available)

If you already have historical PDFs in OneDrive:

```powershell
# Download from OneDrive using existing setup
python scripts/check_recipients.py  # To verify OneDrive access
# Then manually download 2-3 sample files to data/tmp/
```

---

## Verification

After setup, verify everything works:

### 1. Test Website Crawling

```powershell
uv run python scripts/validation/test_website_crawl.py
```

**Expected**:

- ✅ Website accessible
- ✅ Parse edition metadata successfully
- ✅ Discover 480+ editions

**If it fails**:

- Check `BOERSENMEDIEN_COOKIE` in .env
- Verify cookie hasn't expired (update with `update_cookie_mongodb.py`)

---

### 2. Test PDF Parsing

```powershell
uv run python scripts/validation/test_pdf_parsing.py
```

**Expected**:

- ✅ Extract tables from PDFs
- ✅ Parse German number formats
- ✅ Identify Musterdepot table

**If it fails**:

- Ensure PDFs are in `data/tmp/`
- Check PDF format (not scanned/image-only)
- May need to adjust selectors for different years

---

### 3. Test Azure Blob Storage

```powershell
uv run python scripts/validation/test_blob_storage.py
```

**Expected**:

- ✅ Connect to Azure Storage
- ✅ Create test container
- ✅ Upload/download/delete test blob

**If it fails**:

- Check `AZURE_STORAGE_CONNECTION_STRING` in .env
- Verify storage account exists
- Check network connectivity

---

### 4. Test yfinance (Optional - Phase 2)

```powershell
uv run python scripts/validation/test_yfinance.py
```

**Expected**:

- ✅ Fetch prices for German stocks
- ⚠️ Warrants not available (expected)

---

## Troubleshooting

### Cookie Issues

**Problem**: "Authentication required" or redirect to login

**Solution**:

```powershell
# Update cookie in MongoDB
python scripts/update_cookie_mongodb.py

# Re-run setup
uv run python scripts/validation/setup_prerequisites.py
```

---

### Azure Storage Issues

**Problem**: "AZURE_STORAGE_CONNECTION_STRING not set"

**Solution**:

1. Verify `.env` file exists in project root
2. Check connection string format (should start with `DefaultEndpointsProtocol=https`)
3. Reload terminal after editing `.env`

**Problem**: "Unable to connect to Azure Storage"

**Solution**:

1. Test network: `Test-NetConnection depotbutler2025.blob.core.windows.net -Port 443`
2. Check firewall settings
3. Verify storage account is not deleted

---

### PDF Parsing Issues

**Problem**: "No Musterdepot table found"

**Solution**:

1. Open PDF manually - verify it contains the Musterdepot table
2. Check if PDF is text-based (not scanned image)
3. Table structure may have changed - will need to adjust selectors

---

## Ready for Phase 0?

After all validations pass:

✅ **Website crawling** works → Can discover editions
✅ **Azure Blob Storage** works → Can archive PDFs
✅ **PDF parsing** works → Can extract data (Phase 1)

**Next steps**:

1. Review validation results
2. Proceed to Phase 0 implementation:
   - Create `edition_crawler.py` service
   - Create `blob_storage_service.py`
   - Create `collect_historical_pdfs.py` script
3. Start with a small batch (10 editions) to test end-to-end

---

## Cost Estimates

**Azure Storage (Phase 0)**:

- Standard LRS: €0.02/GB/month
- Cool tier: €0.01/GB/month
- 480 editions × ~850KB = 400MB
- Monthly cost: ~€0.004
- 10-year cost: ~€0.50

**MongoDB Atlas** (existing):

- M0 Free tier: 512MB (sufficient)
- If upgrade needed: M2 Shared €8/month

**Total monthly cost**: < €1

---

**Last Updated**: December 26, 2025
**Status**: Ready for validation
