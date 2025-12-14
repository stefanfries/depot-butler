# Migration to HTTPX (December 2025)

## Overview

Successfully migrated from Patchright (browser automation) to HTTPX (HTTP client) for lighter, faster, and more cost-effective scraping.

## Benefits

### Performance

- **60-70% Lower Resource Usage**: No browser overhead
- **~500MB Smaller Docker Image**: From ~700MB to ~200MB
- **Faster Execution**: No browser startup delay (5-10 seconds saved per run)
- **Lower Memory**: ~100MB vs ~300MB with browser

### Cost

- **Reduced Azure Costs**: Lower CPU/memory consumption
- **Faster Deployments**: Smaller image = faster pushes to Azure Container Registry

### Maintainability

- **Simpler Code**: Direct HTTP requests vs browser automation
- **Fewer Dependencies**: Removed 4 packages (patchright, greenlet, pyee, playwright)
- **Easier Debugging**: HTTP logs vs browser traces

## What Changed

### Code Changes

- **New**: `src/depotbutler/httpx_client.py` (371 lines)
- **Updated**: `src/depotbutler/workflow.py` (uses HttpxBoersenmedienClient)
- **Updated**: `src/depotbutler/main.py` (imports httpx_client)
- **Removed**: `src/depotbutler/browser_client.py`
- **Removed**: `src/depotbutler/browser_scraper.py`

### Dependencies

- **Removed**: `patchright>=1.49.0`, `greenlet`, `pyee`
- **Kept**: `httpx>=0.28.1` (already present)
- **Updated**: `uv.lock` (45 packages, down from 48)

### Docker Image

- **Removed**: 40+ lines of browser dependencies (libgtk-3-0, libnss3, webkit libs)
- **Removed**: `patchright install chromium` command
- **Result**: Clean Python 3.13-slim base image

### Testing

- **New**: `tests/test_httpx_client.py` (10 comprehensive tests)
- **Status**: All 63 tests passing ✅

## Authentication Approach

### Before (Patchright)

- Attempted automated login with email/password
- Failed due to disabled "Anmelden" button (Cloudflare Turnstile widget)
- Required manual cookie export anyway

### After (HTTPX)

- Direct cookie-based authentication
- Manual cookie export every 3 days (same as before)
- No Cloudflare challenge detection (cookie bypasses it)
- Simpler and more reliable

## URL Discovery

The HTTPX client constructs edition URLs using:

```text
https://konto.boersenmedien.com/produkte/abonnements/{subscription_id}/{subscription_number}/ausgaben
```

Example:

```text
https://konto.boersenmedien.com/produkte/abonnements/2477462/AM-01029205/ausgaben
```

Then follows links to:

- Edition details: `/produkte/ausgabe/{edition_id}/details`
- PDF download: `/produkte/content/{edition_id}/download`

## HTML Parsing

Uses BeautifulSoup to parse server-rendered HTML:

- Subscription list: `div.subscription-item` with data attributes
- Edition links: `a[href*="/ausgabe/"][href*="/details"]`
- Download links: `a[href*="/download"]`
- Publication dates: `time[datetime]` elements

## Production Validation

Successfully tested locally with full workflow:

- ✅ Authenticated with cookie
- ✅ Discovered 2 subscriptions
- ✅ Found latest edition (Megatrend Folger 49/2025)
- ✅ Downloaded PDF (2.2 MB)
- ✅ Emailed to 5 recipients
- ✅ Uploaded to OneDrive
- ✅ Marked as processed in MongoDB

## Deployment

No special deployment steps needed:

1. Commit changes
2. Push to main
3. GitHub Actions auto-deploys to Azure Container Apps
4. Next scheduled run uses HTTPX client

## Rollback Plan

If issues arise:

1. Revert commit: `git revert HEAD`
2. Push to main
3. Auto-deploys previous version
4. Cookie authentication still works (unchanged)

## Monitoring

Watch for:

- Cookie expiration warnings (3-day cycle)
- Edition discovery failures
- Download errors
- Azure resource usage (should be lower)

## Future Improvements

- Consider caching subscription discovery results
- Add retry logic for transient HTTP errors
- Monitor cookie expiration patterns
- Optimize BeautifulSoup parsing if needed
