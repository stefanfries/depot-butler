# DepotButler Operational Runbook

## Table of Contents

1. [Daily Operations](#daily-operations)
2. [Weekly Tasks](#weekly-tasks)
3. [Monthly Tasks](#monthly-tasks)
4. [Emergency Procedures](#emergency-procedures)
5. [Monitoring & Alerts](#monitoring--alerts)
6. [Incident Response](#incident-response)

---

## Daily Operations

### Morning Check (After 16:30 CET)

**Objective:** Verify yesterday's workflow executed successfully

**Steps:**

1. **Check admin email for notifications**
   - Look for success summary email
   - Check for any error/warning emails
   - Cookie expiry warnings?

2. **Verify metrics in MongoDB**

   ```powershell
   mongosh "$env:MONGODB_CONNECTION_STRING" --eval "
   db.metrics.find().sort({timestamp: -1}).limit(1).pretty()
   "
   ```

  **Expected:** Entry from previous day (~16:00 CET)

  **Success indicators:**

   - `status: "success"`
   - `total_publications >= 2`
   - `successful_count >= 0`
   - Recent timestamp

3. **Check Azure Container Apps execution**

   ```powershell
   az containerapp job execution list \
     --name depotbutler-job \
     --resource-group <resource-group> \
     --query "[0].{name:name, status:properties.status, startTime:properties.startTime}" \
     -o table
   ```

   **Expected:** Status = "Succeeded", recent start time

4. **Spot check recipient inbox**
   - Verify at least one recipient received publication
   - Check OneDrive folder for uploads
   - Confirm file naming correct (YYYY-MM-DD_Title_Issue.pdf)

**If Issues Found:**

- See [Troubleshooting Guide](TROUBLESHOOTING.md)
- Check [Emergency Procedures](#emergency-procedures)

---

### New Edition Published

**Trigger:** New edition available on boersenmedien.com

**What Happens:**

- Workflow runs daily at 16:00 CET
- Automatically detects new editions
- Downloads, distributes, and tracks

**Manual Intervention Not Needed** - System is fully automated

**Optional Manual Run:**

```powershell
# Trigger workflow immediately (if can't wait until 16:00)
az containerapp job start \
  --name depotbutler-job \
  --resource-group <resource-group>
```

---

### Recipient Requests

#### Add New Recipient

```powershell
# 1. Add recipient to MongoDB (manual or via UI)
# Document structure in docs/MONGODB.md

# 2. Add publication preferences
uv run python scripts/manage_recipient_preferences.py add \
  new.user@example.com megatrend-folger

# 3. Verify setup
uv run python scripts/manage_recipient_preferences.py list \
  new.user@example.com

# 4. Activate if needed
uv run python scripts/manage_recipient_preferences.py activate \
  new.user@example.com
```

#### Remove Recipient

```powershell
# Option 1: Deactivate (preserves data)
uv run python scripts/manage_recipient_preferences.py deactivate \
  user@example.com

# Option 2: Remove preferences (more thorough)
uv run python scripts/manage_recipient_preferences.py remove \
  user@example.com megatrend-folger

# Option 3: Delete from MongoDB (permanent)
mongosh "$env:MONGODB_CONNECTION_STRING" --eval "
db.recipients.deleteOne({email: 'user@example.com'})
"
```

**Recommendation:** Use deactivate (Option 1) to preserve history

#### Update Recipient Preferences

```powershell
# Disable email (use OneDrive only)
uv run python scripts/manage_recipient_preferences.py remove \
  user@example.com aktionaer-epaper
uv run python scripts/manage_recipient_preferences.py add \
  user@example.com aktionaer-epaper --no-email

# Add new publication
uv run python scripts/manage_recipient_preferences.py add \
  user@example.com new-publication-id

# View current settings
uv run python scripts/manage_recipient_preferences.py list \
  user@example.com
```

---

## Weekly Tasks

### Monday: System Health Check

**Objective:** Ensure system running smoothly over past week

**Steps:**

1. **Review metrics trends**

   ```powershell
   # Last 7 days of runs
   mongosh "$env:MONGODB_CONNECTION_STRING" --eval "
   db.metrics.find({
     timestamp: { \$gte: new Date(Date.now() - 7*24*60*60*1000) }
   }).sort({timestamp: -1}).pretty()
   "
   ```

   **Look for:**
   - Any failed runs (status != "success")
   - Processing time trends (should be consistent)
   - Skipped publications (already processed is normal)

2. **Check error logs**

   ```powershell
   # Azure Container Apps logs (last 7 days)
   az containerapp job execution list \
     --name depotbutler-job \
     --resource-group <resource-group> \
     --query "[?properties.status!='Succeeded'].{name:name, status:properties.status, startTime:properties.startTime}" \
     -o table
   ```

3. **Verify recipient statistics**

   ```powershell
   uv run python scripts/manage_recipient_preferences.py stats
   ```

   **Check:**
   - All active recipients have preferences (100% coverage)
   - No warnings about missing preferences
   - Delivery method distribution as expected

4. **Test email deliverability**
   - Check spam folder on test account
   - Verify emails not being filtered
   - Check sender reputation if available

**If Issues Found:**

- Document in incident log
- See [Troubleshooting Guide](TROUBLESHOOTING.md)

---

### Wednesday: Cookie Check

**Objective:** Ensure authentication will not expire

**Steps:**

1. **Check cookie expiry**

   ```powershell
   uv run python scripts/cookie_checker.py
   ```

   **Expected:** "Cookie valid for X days"

2. **If <3 days remaining:**

   ```powershell
   # Refresh cookie
   uv run python scripts/update_cookie_mongodb.py
   ```

   **Follow prompts to:**
   - Login to boersenmedien.com in browser
   - Copy cookie value
   - Paste into script
   - Verify saved to MongoDB

3. **Verify new cookie works**

   ```powershell
   uv run python -m depotbutler --dry-run
   ```

   **Expected:** "✓ Authenticated successfully"

**Why Weekly:**

- Cookie expires every ~2 weeks
- Check mid-week ensures not surprised on weekend
- Wednesday gives buffer to fix issues

---

### Friday: Database Maintenance

**Objective:** Keep database healthy and within limits

**Steps:**

1. **Check database size**

   ```powershell
   mongosh "$env:MONGODB_CONNECTION_STRING" --eval "
   db.stats(1024*1024)
   "
   ```

   **Expected:** dataSize < 400MB (free tier limit is 512MB)

2. **Count documents per collection**

   ```powershell
   mongosh "$env:MONGODB_CONNECTION_STRING" --eval "
   print('Publications:', db.publications.countDocuments({}));
   print('Recipients:', db.recipients.countDocuments({}));
   print('Processed Editions:', db.processed_editions.countDocuments({}));
   print('Metrics:', db.metrics.countDocuments({}));
   print('Config:', db.config.countDocuments({}));
   "
   ```

3. **Archive old metrics (if needed)**

   ```powershell
   # Keep last 90 days of metrics
   mongosh "$env:MONGODB_CONNECTION_STRING" --eval "
   db.metrics.deleteMany({
     timestamp: { \$lt: new Date(Date.now() - 90*24*60*60*1000) }
   })
   "
   ```

4. **Archive old editions (if enabled)**

   ```powershell
   # Check retention policy (default: 90 days)
   mongosh "$env:MONGODB_CONNECTION_STRING" --eval "
   db.processed_editions.find().sort({date: 1}).limit(1).pretty()
   "
   ```

   **Note:** Auto-cleanup via retention policy (90 days)

**If Database >450MB:**

- Archive metrics more aggressively (30 days)
- Consider exporting to Azure Blob Storage
- Review need for upgrade to paid tier

---

## Monthly Tasks

### First Monday: Subscription Review

**Objective:** Ensure all subscriptions active and up-to-date

**Steps:**

1. **Review publication status**

   ```powershell
   mongosh "$env:MONGODB_CONNECTION_STRING" --eval "
   db.publications.find({}, {
     name: 1,
     publication_id: 1,
     active: 1,
     duration_start: 1,
     duration_end: 1
   }).pretty()
   "
   ```

2. **Check for expiring subscriptions**
   - Look at `duration_end` dates
   - Any ending in next 30 days?
   - Renew on boersenmedien.com if needed

3. **Verify subscription count**
   - Login to boersenmedien.com
   - Check "Meine Abonnements"
   - Compare with MongoDB `publications` collection
   - Should have 2 active subscriptions (or as expected)

4. **Run discovery sync**

   ```powershell
   uv run python -m depotbutler
   ```

   **Expected:** "✓ Publication sync complete: X total, Y updated"

---

### Mid-Month: Recipient Audit

**Objective:** Ensure recipient list is accurate

**Steps:**

1. **Review recipient statistics**

   ```powershell
   uv run python scripts/manage_recipient_preferences.py stats
   ```

2. **Check for inactive recipients**

   ```powershell
   uv run python scripts/check_recipients.py
   ```

   **Questions:**
   - Any inactive that should be removed?
   - Any active that no longer want service?
   - Any missing preferences?

3. **Verify delivery success**

   ```powershell
   mongosh "$env:MONGODB_CONNECTION_STRING" --eval "
   db.recipients.find({
     last_sent_at: { \$lt: new Date(Date.now() - 7*24*60*60*1000) }
   }, {email: 1, last_sent_at: 1, active: 1}).pretty()
   "
   ```

   **Flag:** Recipients not sent to in last week (should be rare)

4. **Contact recipients for feedback**
   - Are they receiving publications?
   - Any issues with delivery?
   - Preferences correct?

---

### End of Month: Backup & Documentation

**Objective:** Ensure disaster recovery possible

**Steps:**

1. **Export MongoDB data**

   ```powershell
   # Export recipients (most important)
   mongodump --uri="$env:MONGODB_CONNECTION_STRING" \
     --collection=recipients \
     --out=backups/$(Get-Date -Format 'yyyy-MM')

   # Export publications
   mongodump --uri="$env:MONGODB_CONNECTION_STRING" \
     --collection=publications \
     --out=backups/$(Get-Date -Format 'yyyy-MM')
   ```

2. **Store backups securely**
   - Azure Blob Storage (encrypted)
   - Local encrypted backup
   - Keep last 3 months

3. **Review documentation**
   - Any procedures that need updating?
   - New issues to add to troubleshooting?
   - Architecture changes to document?

4. **Update MASTER_PLAN.md**
   - Mark completed sprints
   - Adjust priorities based on learnings
   - Document any decisions made

---

## Emergency Procedures

### Critical: Workflow Completely Failed

**Symptoms:**

- No execution in Azure Container Apps
- No metrics in MongoDB for >24 hours
- Multiple admin error emails

**Immediate Actions:**

1. **Check Azure Container Apps status**

   ```powershell
   az containerapp job show \
     --name depotbutler-job \
     --resource-group <resource-group> \
     --query "properties.{provisioningState:provisioningState, scheduleTriggerConfig:configuration.scheduleTriggerConfig}"
   ```

2. **Review logs**

   ```powershell
   az containerapp job execution list \
     --name depotbutler-job \
     --resource-group <resource-group> \
     --query "[0].{name:name, status:properties.status}" \
     -o table

   az containerapp job execution logs show \
     --name <execution-name> \
     --resource-group <resource-group>
   ```

3. **Manual workflow run**

   ```powershell
   # Test locally first
   uv run python -m depotbutler --dry-run

   # If successful, trigger in Azure
   az containerapp job start \
     --name depotbutler-job \
     --resource-group <resource-group>
   ```

4. **If still failing:**
   - Check cookie status (most common issue)
   - Verify MongoDB connection
   - Check OneDrive authentication
   - Review [Troubleshooting Guide](TROUBLESHOOTING.md)

**Recovery Time Objective (RTO):** 4 hours

---

### High: Authentication Expired

**Symptoms:**

- "Cookie expired" errors
- All downloads failing
- Workflow ends early

**Immediate Actions:**

1. **Update cookie**

   ```powershell
   uv run python scripts/update_cookie_mongodb.py
   ```

2. **Verify authentication**

   ```powershell
   uv run python -m depotbutler --dry-run
   ```

3. **Manual run if needed**

   ```powershell
   az containerapp job start \
     --name depotbutler-job \
     --resource-group <resource-group>
   ```

**Recovery Time Objective (RTO):** 15 minutes

---

### Medium: Email Delivery Failed

**Symptoms:**

- "Failed to send email" errors
- Recipients not receiving publications
- SMTP connection errors

**Immediate Actions:**

1. **Check SMTP credentials**

   ```powershell
   echo $env:SMTP_HOST
   echo $env:SMTP_PORT
   echo $env:SMTP_USERNAME
   # Verify password in .env
   ```

2. **Test email send**

   ```powershell
   # Run workflow in dry-run (still sends test emails)
   uv run python -m depotbutler --dry-run
   ```

3. **Temporary workaround**
   - Use OneDrive-only delivery
   - Disable email for affected publications
   ```powershell
   uv run python scripts/manage_recipient_preferences.py bulk-add \
     publication-id --no-email
   ```

4. **Fix SMTP**
   - Update credentials in Azure Container Apps environment variables
   - Test with external SMTP service if GMX down

**Recovery Time Objective (RTO):** 1 hour

---

### Low: OneDrive Upload Failed

**Symptoms:**

- Upload errors for some recipients
- Timeout during large file upload
- Rate limit errors

**Immediate Actions:**

1. **Check if transient**
   - Wait 1 hour
   - Retry workflow

   ```powershell
   az containerapp job start \
     --name depotbutler-job \
     --resource-group <resource-group>
   ```

2. **Re-authenticate OneDrive**

   ```powershell
   uv run python scripts/setup_onedrive_auth.py
   ```

3. **Check folder paths**

   ```powershell
   uv run python scripts/check_recipients.py
   ```

   - Verify `custom_onedrive_folder` exists

4. **Temporary workaround**
   - Use email delivery instead
   - Manual upload to OneDrive
   - Fix folder paths in recipient preferences

**Recovery Time Objective (RTO):** 2 hours

---

## Monitoring & Alerts

### Key Metrics to Monitor

1. **Workflow Success Rate**
   - Target: >99% (1 failure per 100 runs acceptable)
   - Alert: 2 consecutive failures

2. **Processing Time**
   - Baseline: 2-5 minutes per workflow
   - Alert: >10 minutes

3. **Email Delivery Rate**
   - Target: 100% for valid addresses
   - Alert: <95%

4. **OneDrive Upload Success Rate**
   - Target: >95% (some transient failures acceptable)
   - Alert: <80%

5. **Database Size**
   - Target: <400MB (80% of free tier)
   - Alert: >450MB

6. **Cookie Expiry**
   - Warning: 3 days before expiry
   - Critical: 1 day before expiry

### Setting Up Alerts

**Azure Monitor:**

```powershell
# Create alert for job failures
az monitor metrics alert create \
  --name depotbutler-job-failures \
  --resource-group <resource-group> \
  --scopes <container-app-id> \
  --condition "count failed-executions > 1" \
  --window-size 1d \
  --evaluation-frequency 1h \
  --action-group <action-group-id>
```

**MongoDB Atlas:**

- Enable alerts for:
  - Database size >80%
  - Connection failures
  - Query performance degradation

**Email Monitoring:**

- Check admin inbox for error emails
- Set up inbox rules to highlight errors

---

## Incident Response

### Incident Log Template

```markdown
## Incident: [Short Description]

**Date:** YYYY-MM-DD HH:MM CET
**Severity:** Critical / High / Medium / Low
**Status:** Investigating / Mitigated / Resolved

### Timeline

- HH:MM - Issue detected
- HH:MM - Investigation started
- HH:MM - Root cause identified
- HH:MM - Mitigation applied
- HH:MM - Issue resolved

### Symptoms

- What was observed?
- What alerts fired?
- User reports?

### Root Cause

- What caused the issue?
- Why wasn't it caught earlier?

### Resolution

- Steps taken to fix
- Temporary vs permanent fix

### Prevention

- What changes will prevent recurrence?
- Monitoring improvements?
- Documentation updates?

### Action Items

- [ ] Update documentation
- [ ] Implement monitoring
- [ ] Code changes needed?
```

### Post-Incident Review

**Within 24 hours:**

1. Complete incident log
2. Identify root cause
3. Document resolution
4. List action items

**Within 1 week:**

1. Implement prevention measures
2. Update documentation
3. Update monitoring
4. Share learnings

---

## Maintenance Windows

### Scheduled Maintenance

**When:** First Sunday of month, 08:00-10:00 CET
**Why:** No publications released on Sunday mornings

**Activities:**

- Azure updates
- Database maintenance
- Dependency updates
- Testing

**Procedure:**

1. Disable scheduled job
2. Perform maintenance
3. Test manually
4. Re-enable scheduled job
5. Monitor first run

---

## Related Documentation

- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Detailed error resolution
- [PRODUCTION_RUN_CHECKLIST.md](PRODUCTION_RUN_CHECKLIST.md) - Pre-deployment checklist
- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment procedures
- [CONFIGURATION.md](CONFIGURATION.md) - Configuration guide
- [MONGODB.md](MONGODB.md) - Database schema and operations

---

## Contacts

### Admin Team

- **Primary Admin:** (Configure in `.env`)
- **Email:** Set in `ADMIN_NOTIFICATION_EMAILS`
- **On-Call:** Receive all error notifications

### External Services

- **MongoDB Atlas Support:** <support@mongodb.com>
- **Azure Support:** Azure Portal → Help + Support
- **Microsoft Graph API:** https://developer.microsoft.com/graph

### Escalation

1. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
2. Review incident log for similar issues
3. Check GitHub issues: https://github.com/stefanfries/depot-butler/issues
4. Contact admin team
