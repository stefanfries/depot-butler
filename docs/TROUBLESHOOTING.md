# DepotButler Troubleshooting Guide

## Quick Reference

| Issue | First Check | Solution |
|-------|-------------|----------|
| Workflow fails | Cookie expired? | Run `update_cookie_mongodb.py` |
| No emails sent | SMTP credentials? | Check `.env` SMTP_* variables |
| Upload fails | OneDrive token? | Run `setup_onedrive_auth.py` |
| Wrong timezone | Publication times off? | All times stored as UTC |
| Tests failing | Dependencies? | `uv sync` to update |

---

## Authentication Issues

### Cookie Expired

**Symptoms:**

- Workflow fails with "❌ Authentication failed"
- HTTP 401 or 403 errors from boersenmedien.com
- Log shows "Cookie expired" or "Unauthorized"

**Diagnosis:**

```powershell
# Check cookie expiry
uv run python scripts/cookie_checker.py
```

**Solution:**

```powershell
# Update cookie in MongoDB
uv run python scripts/update_cookie_mongodb.py
```

**Prevention:**

- Cookie warning emails sent 3 days before expiry
- Set up reminders to refresh cookie every 2 weeks
- Monitor admin email for expiry warnings

**Root Cause:**

- boersenmedien.com session cookies expire after ~2 weeks
- No programmatic way to refresh (requires browser login)

---

### OneDrive Authentication Failed

**Symptoms:**

- Upload fails with "Authentication failed"
- Error: "invalid_grant" or "expired_token"
- OneDrive uploads skip all recipients

**Diagnosis:**

```powershell
# Test OneDrive connection
uv run python scripts/setup_onedrive_auth.py
```

**Solution:**

1. Re-authenticate with Microsoft:

   ```powershell
   uv run python scripts/setup_onedrive_auth.py
   ```

2. Follow browser OAuth flow
3. New refresh token saved to MongoDB
4. Restart workflow

**Prevention:**

- Refresh tokens are long-lived (90 days)
- Monitor OneDrive upload errors in metrics
- Keep backup of OneDrive app credentials

**Root Cause:**

- Microsoft Graph API refresh tokens can expire
- Token revoked if not used for 90 days

---

## Database Issues

### MongoDB Connection Failed

**Symptoms:**

- Workflow fails at startup
- Error: "Failed to connect to MongoDB"
- Timeout connecting to MongoDB Atlas

**Diagnosis:**

```powershell
# Check connection string
echo $env:MONGODB_CONNECTION_STRING

# Test connection
uv run python -c "from depotbutler.db.mongodb import get_mongodb_service; import asyncio; asyncio.run(get_mongodb_service())"
```

**Solution:**

1. Verify `MONGODB_CONNECTION_STRING` in `.env`
2. Check MongoDB Atlas cluster is running (not paused)
3. Verify IP whitelist allows your IP (or 0.0.0.0/0 for Azure)
4. Test credentials in MongoDB Atlas

**Prevention:**

- Use MongoDB Atlas free tier (always-on)
- Whitelist 0.0.0.0/0 for production (Azure Container Apps)
- Keep backup of connection string

---

### Collection Not Found

**Symptoms:**

- Error: "Collection 'X' does not exist"
- Empty results from database queries
- Missing configuration or recipients

**Diagnosis:**

```powershell
# List collections
mongosh "$env:MONGODB_CONNECTION_STRING" --eval "db.getCollectionNames()"
```

**Solution:**

```powershell
# Initialize database
uv run python scripts/init_app_config.py

# Seed publications
uv run python scripts/seed_publications.py
```

**Prevention:**

- Run initialization scripts before first production run
- Document database setup in README

---

## Download Issues

### Edition Not Found

**Symptoms:**

- "⚠️ No editions found" for publication
- Publication skipped in workflow
- Website shows edition but script doesn't find it

**Diagnosis:**

```powershell
# Check publication status
uv run python scripts/check_recipients.py --stats

# Test discovery
uv run python -m depotbutler --dry-run
```

**Solution:**

1. **Check publication active status:**

   ```powershell
   # View publications in MongoDB
   mongosh "$env:MONGODB_CONNECTION_STRING" --eval "db.publications.find({active: true})"
   ```

2. **Website structure changed:**
   - Review HTML structure at boersenmedien.com
   - Update selectors in `httpx_client.py` if needed
   - Check edition details URL format

3. **Subscription expired:**
   - Verify subscription duration in MongoDB
   - Check boersenmedien.com account for active subscriptions

**Prevention:**

- Monitor discovery service logs for parsing errors
- Set up alerts for "no editions found" errors
- Regular manual verification of website structure

---

### Download Timeout

**Symptoms:**

- Error: "Download timeout after 120s"
- Large PDFs fail to download
- Network timeout errors

**Diagnosis:**

```powershell
# Test download with verbose logging
$env:LOG_LEVEL="DEBUG"
uv run python -m depotbutler
```

**Solution:**

1. **Increase timeout** (in `httpx_client.py`):

   ```python
   timeout = httpx.Timeout(timeout=300.0)  # 5 minutes
   ```

2. **Check network connectivity:**
   - Test from same network as production
   - Verify no firewall blocking

3. **Retry manually:**

   ```powershell
   # Workflow will retry on next run
   uv run python -m depotbutler
   ```

**Prevention:**

- Set appropriate timeout for large files (DER AKTIONÄR E-Paper is ~25MB)
- Monitor download times in metrics
- Consider implementing resumable downloads

---

## Email Issues

### Emails Not Sent

**Symptoms:**

- No error, but recipients don't receive emails
- SMTP connection successful but no delivery
- Emails in spam folder

**Diagnosis:**

```powershell
# Check SMTP configuration
echo $env:SMTP_HOST
echo $env:SMTP_PORT
echo $env:SMTP_USERNAME

# Test email send (check inbox)
uv run python -m depotbutler --dry-run
```

**Solution:**

1. **Verify SMTP credentials:**
   - Check `.env` has correct SMTP_* variables
   - Test credentials in email client

2. **Check spam folder:**
   - Emails may be filtered
   - Add sender to whitelist

3. **Email size limit:**
   - SMTP servers limit attachment size (~25MB)
   - DER AKTIONÄR E-Paper too large for email (OneDrive only)

4. **Recipient email invalid:**

   ```powershell
   uv run python scripts/check_recipients.py
   ```

**Prevention:**

- Test email delivery regularly
- Use OneDrive for large files (>10MB)
- Monitor bounce rates
- Keep valid email addresses in recipients collection

---

### Attachment Too Large

**Symptoms:**

- Email fails with "Message too large"
- SMTP server rejects email
- DER AKTIONÄR E-Paper emails fail

**Diagnosis:**

```powershell
# Check file sizes
ls data/tmp/*.pdf | Select-Object Name, Length
```

**Solution:**

1. **Use OneDrive only for large files:**
   ```powershell
   # Disable email for specific publication
   uv run python scripts/manage_recipient_preferences.py bulk-add der-aktionaer-epaper --no-email
   ```

2. **Configure publication-level settings:**
   - Set `email_enabled: false` in MongoDB for large publications
   - Use OneDrive delivery instead

**Prevention:**

- DER AKTIONÄR E-Paper always OneDrive-only (>25MB)
- Megatrend Folger safe for email (~2MB)
- Monitor file sizes in metrics

---

## Upload Issues

### OneDrive Upload Failed

**Symptoms:**

- Error: "Upload failed" for one or more recipients
- Timeout during upload
- Rate limit exceeded

**Diagnosis:**

```powershell
# Check OneDrive logs
$env:LOG_LEVEL="DEBUG"
uv run python -m depotbutler
```

**Solution:**

1. **Timeout (large files):**
   - Normal for 25MB files with chunked upload
   - Retry automatically on next run

2. **Folder not found:**

   ```powershell
   # Verify folder path in recipient settings
   uv run python scripts/check_recipients.py
   ```

3. **Rate limit:**
   - Microsoft Graph API limits uploads
   - Wait 1 hour and retry
   - Sequential processing helps avoid rate limits

4. **Invalid folder path:**
   - Check `custom_onedrive_folder` in recipient preferences
   - Ensure folder exists in OneDrive

**Prevention:**

- Use chunked upload for files ≥4MB (implemented)
- Sequential publication processing (implemented)
- Retry logic for transient errors (implemented)

---

## Testing Issues

### Tests Failing

**Symptoms:**

- `pytest` fails with import errors
- AsyncMock errors
- Database connection errors during tests

**Diagnosis:**

```powershell
# Run tests with verbose output
uv run pytest -v

# Run specific test
uv run pytest tests/test_workflow.py::test_specific_function -v
```

**Solution:**

1. **Update dependencies:**

   ```powershell
   uv sync
   ```

2. **Check test environment:**
   - Tests use `.env.test` not `.env`
   - MongoDB not required for unit tests (mocked)

3. **Integration tests require MongoDB:**

   ```powershell
   # Skip integration tests
   uv run pytest -m "not integration"
   ```

4. **Mock structure issues:**
   - Ensure mocks match actual implementation
   - Use `AsyncMock` for async functions

**Prevention:**

- Run tests before committing (pre-commit hook)
- Keep test dependencies updated
- Document test requirements in README

---

### Pre-commit Hooks Failing

**Symptoms:**

- Git commit blocked
- Ruff linting errors
- Mypy type checking errors

**Diagnosis:**

```powershell
# Run pre-commit manually
pre-commit run --all-files
```

**Solution:**

1. **Ruff errors:**

   ```powershell
   # Auto-fix formatting
   uv run ruff format .

   # Check for remaining issues
   uv run ruff check .
   ```

2. **Mypy errors:**

   ```powershell
   # Check type hints
   uv run mypy src/
   ```

   - Add missing type hints
   - Fix type inconsistencies

3. **Line ending issues:**
   - Pre-commit will auto-fix CRLF/LF
   - Commit again after fix

**Prevention:**

- Install pre-commit hooks: `pre-commit install`
- Run `ruff format` before committing
- Keep type hints on all functions

---

## Production Issues

### Workflow Not Running on Schedule

**Symptoms:**

- No workflow execution at scheduled time
- Azure Container Apps job not triggered
- No recent metrics in MongoDB

**Diagnosis:**

```powershell
# Check Azure Container Apps logs
az containerapp job execution list --name depotbutler-job --resource-group <rg>

# Check last run metrics
mongosh "$env:MONGODB_CONNECTION_STRING" --eval "db.metrics.find().sort({timestamp: -1}).limit(1)"
```

**Solution:**

1. **Check job schedule:**

   ```powershell
   az containerapp job show --name depotbutler-job --resource-group <rg> --query "properties.configuration.scheduleTriggerConfig"
   ```

2. **Verify job is enabled:**
   - Check Azure Portal → Container Apps → depotbutler-job
   - Ensure not paused or disabled

3. **Check execution history:**
   - Azure Portal → Container Apps → Executions
   - Review logs for errors

4. **Manual trigger:**

   ```powershell
   az containerapp job start --name depotbutler-job --resource-group <rg>
   ```

**Prevention:**

- Monitor metrics collection (should have daily entries)
- Set up Azure alerts for job failures
- Review execution logs weekly

---

### Edition Already Processed (False Positive)

**Symptoms:**

- Edition skipped with "✅ Already processed"
- New edition available but not downloaded
- `processed_editions` collection has duplicate entries

**Diagnosis:**

```powershell
# Check processed editions
mongosh "$env:MONGODB_CONNECTION_STRING" --eval "db.processed_editions.find({publication_id: 'megatrend-folger'}).sort({date: -1}).limit(5)"
```

**Solution:**

1. **Delete incorrect entry:**
   ```javascript
   // In mongosh
   db.processed_editions.deleteOne({
     _id: "2025-12-18_megatrend-folger"
   })
   ```

2. **Re-run workflow:**

   ```powershell
   uv run python -m depotbutler
   ```

**Prevention:**

- Edition tracking uses `{date}_{publication_id}` as unique key
- Should not have false positives unless date parsing wrong
- Review edition detection logic if recurring

---

## Performance Issues

### Slow Workflow Execution

**Symptoms:**

- Workflow takes >5 minutes to complete
- Timeouts during processing
- High memory usage

**Diagnosis:**

```powershell
# Run with timing metrics
$env:LOG_LEVEL="DEBUG"
Measure-Command { uv run python -m depotbutler }
```

**Solution:**

1. **Large PDF downloads:**
   - Normal for DER AKTIONÄR E-Paper (~25MB)
   - Use blob storage cache to avoid re-downloading

2. **Multiple recipients:**
   - OneDrive uploads are sequential (by design)
   - Each upload ~10-30 seconds for large files

3. **Network latency:**
   - Check network speed
   - Consider Azure regions closer to data sources

**Optimization:**

- Enable PDF caching (implemented in Sprint 5)
- Sequential processing prevents rate limits
- Chunked uploads for large files

---

## Dry-Run Mode Issues

### Dry-Run Still Sends Emails/Uploads

**Symptoms:**

- `--dry-run` flag doesn't prevent side effects
- Emails sent during testing
- Files uploaded to OneDrive

**Diagnosis:**

```powershell
# Check dry-run implementation
grep -r "dry_run" src/
```

**Solution:**

- **Current implementation:** Dry-run downloads PDFs but skips email/upload
- **Expected behavior:** No side effects except download

**Prevention:**

- Use `test_dry_run.py` script for safe testing
- Review dry-run guards in code
- Document dry-run behavior

---

## Data Issues

### Recipient Not Receiving Publications

**Symptoms:**

- Recipient reports not receiving publications
- Other recipients receive successfully
- No error in logs

**Diagnosis:**

```powershell
# Check recipient configuration
uv run python scripts/manage_recipient_preferences.py list user@example.com

# Check recipient status
uv run python scripts/check_recipients.py
```

**Solution:**

1. **Recipient inactive:**

   ```powershell
   uv run python scripts/manage_recipient_preferences.py activate user@example.com
   ```

2. **Missing preferences:**

   ```powershell
   uv run python scripts/manage_recipient_preferences.py add user@example.com megatrend-folger
   ```

3. **Delivery disabled:**

   ```powershell
   # Check email_enabled and upload_enabled in preferences
   uv run python scripts/manage_recipient_preferences.py list user@example.com
   ```

**Prevention:**

- Use `stats` command to identify recipients without preferences
- Regular audit of recipient status
- Monitor delivery metrics

---

## Common Error Messages

### "ConnectionTimeoutError: timed out"

**Cause:** Network timeout connecting to external service
**Solution:** Retry, check network connectivity
**Prevention:** Increase timeout in httpx client

### "AuthenticationError: Cookie expired"

**Cause:** boersenmedien.com session cookie expired
**Solution:** Run `update_cookie_mongodb.py`
**Prevention:** Set up reminders every 2 weeks

### "EditionNotFoundError: No editions available"

**Cause:** No new edition published yet, or scraping failed
**Solution:** Check website manually, review HTML structure
**Prevention:** Monitor discovery service logs

### "UploadError: Failed to upload to OneDrive"

**Cause:** OneDrive authentication failed or rate limit
**Solution:** Re-authenticate, wait and retry
**Prevention:** Sequential uploads, chunked for large files

### "ConfigurationError: Missing required setting"

**Cause:** Environment variable not set
**Solution:** Check `.env` file has all required variables
**Prevention:** Use `.env.example` template

---

## Getting Help

### Logs

**View logs:**

```powershell
# Local
uv run python -m depotbutler

# Azure
az containerapp job execution logs show --name depotbutler-job --resource-group <rg>
```

**Set log level:**

```powershell
$env:LOG_LEVEL="DEBUG"
uv run python -m depotbutler
```

### Database Inspection

**MongoDB shell:**

```powershell
mongosh "$env:MONGODB_CONNECTION_STRING"

# Useful commands:
db.publications.find({})
db.recipients.find({})
db.processed_editions.find().sort({date: -1}).limit(10)
db.metrics.find().sort({timestamp: -1}).limit(5)
db.config.find({})
```

### Admin Scripts

```powershell
# Check system status
uv run python scripts/check_recipients.py --stats
uv run python scripts/cookie_checker.py

# Test workflow without side effects
uv run python -m depotbutler --dry-run

# View preferences
uv run python scripts/manage_recipient_preferences.py stats
```

### Contact

- **Admin Email**: Configured in `ADMIN_NOTIFICATION_EMAILS`
- **Repository**: <https://github.com/stefanfries/depot-butler>
- **Documentation**: `docs/` directory

---

## Related Documentation

- [PRODUCTION_RUN_CHECKLIST.md](PRODUCTION_RUN_CHECKLIST.md) - Pre-deployment checklist
- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment procedures
- [CONFIGURATION.md](CONFIGURATION.md) - Configuration guide
- [TESTING.md](TESTING.md) - Testing guide
