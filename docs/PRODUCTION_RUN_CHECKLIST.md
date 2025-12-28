# Production Run Verification Checklist

**Date**: December 28, 2025
**Run Type**: Manual Test Run
**Purpose**: Verify all Sprint 5 features working in production

---

## Pre-Run Information

- [ ] **Job Name**: depot-butler-job
- [ ] **Schedule**: Mon-Fri 3:00 PM UTC (4:00 PM CET)
- [ ] **Run Time**: _________________ (UTC/CET)
- [ ] **Expected Publications**: Megatrend Folger, DER AKTIONÄR E-Paper

---

## 1. Azure Container App Job Execution

### Job Status

- [ ] Job completed successfully (provisioningState: Succeeded)
- [ ] Execution duration: ____________ seconds
- [ ] No error exit code (exit code: 0)

**How to Check:**

```powershell
# View job execution history
az containerapp job execution list \
  --name depot-butler-job \
  --resource-group depot-butler-rg \
  --output table

# Get logs from last execution
az containerapp job logs show \
  --name depot-butler-job \
  --resource-group depot-butler-rg
```

### Container Logs Review

- [ ] Login successful (no authentication errors)
- [ ] Subscriptions discovered successfully
- [ ] Publications synced to MongoDB
- [ ] Each publication processed (download → email → OneDrive → blob)
- [ ] No Python exceptions or stack traces
- [ ] Final "Workflow completed successfully" message

**Key Log Patterns to Look For:**

```text
✓ Logged in successfully
✓ Discovered subscriptions: X
✓ Synced publications to database
✓ Processing publication: [publication-name]
✓ Downloaded edition: [filename]
✓ Sent PDF to X recipient(s)
✓ Uploaded to OneDrive for X recipient(s)
✓ Archived to blob storage
✓ Workflow completed successfully
```

---

## 2. Edition Processing

### Download & Temp Storage

- [ ] PDF downloaded successfully
- [ ] File size reasonable (e.g., Megatrend ~700KB, Aktionär ~20-30MB)
- [ ] File stored in `/mnt/data/tmp/` (volume mount working)
- [ ] Temp file cleaned up after processing

### Edition Metadata

**For each publication processed:**

| Publication | Date | Issue | Filename | Size | Status |
| ----------- | ---- | ----- | -------- | ---- | ------ |
| Megatrend Folger | YYYY-MM-DD | ## | ____________.pdf | ____KB | ✓/✗ |
| DER AKTIONÄR | YYYY-MM-DD | ## | ____________.pdf | ____MB | ✓/✗ |

---

## 3. Email Delivery

### Recipient Email Verification

- [ ] All expected recipients received emails
- [ ] Email subject line correct: "📰 [Publication Title] - Ausgabe [Issue]"
- [ ] PDF attachment present (for Megatrend Folger)
- [ ] OneDrive link present in email body
- [ ] Email sent from: <depot-butler@stefanfries.net>
- [ ] No bounce-back messages

**Check Your Inbox:**

- [ ] Received: Megatrend Folger (with PDF attachment)
- [ ] PDF opens correctly
- [ ] OneDrive link works

**Expected Recipients:**

| Email | Megatrend | Aktionär | Received? |
| ----- | --------- | -------- | --------- |
| <stefan.fries@outlook.com> | ✓ | ✓ (OneDrive only) | ☐ |
| [other recipients...] | ✓/✗ | ✓/✗ | ☐ |

### Email Content Quality

- [ ] Greeting uses first name (e.g., "Hallo Stefan,")
- [ ] Publication title formatted correctly
- [ ] Issue number displayed
- [ ] OneDrive link clickable
- [ ] Professional formatting (HTML rendering)

---

## 4. OneDrive Upload

### Folder Structure

- [ ] Base folder exists: `Publications_DepotButler/`
- [ ] Year subfolder created: `Publications_DepotButler/2025/`
- [ ] Files uploaded with correct naming convention

**Expected Files:**

```text
Publications_DepotButler/
└── 2025/
    ├── YYYY-MM-DD_Megatrend-Folger_##-2025.pdf
    └── YYYY-MM-DD_Der-Aktionaer-E-Paper_##-2025.pdf
```

### File Verification

- [ ] Login to OneDrive web interface
- [ ] Navigate to `Publications_DepotButler/2025/`
- [ ] Both PDFs visible with correct dates
- [ ] File sizes match downloaded editions
- [ ] Files open correctly in browser

**OneDrive File Details:**

| Filename | Size | Upload Time | Opens? |
| -------- | ---- | ----------- | ------ |
| ________________.pdf | ____KB/MB | HH:MM | ☐ |
| ________________.pdf | ____KB/MB | HH:MM | ☐ |

### Upload Method Used

- [ ] Megatrend Folger: Simple upload (< 4MB)
- [ ] DER AKTIONÄR: Chunked upload (≥ 4MB)

---

## 5. Blob Storage Archival

### Azure Portal Check

1. Navigate to: Azure Portal → `depotbutlerarchive` storage account
2. Containers → `editions`

**Expected Blob Structure:**

```text
editions/
└── 2025/
    ├── megatrend-folger/
    │   └── YYYY-MM-DD_Megatrend-Folger_##-2025.pdf
    └── der-aktionaer-e-paper/
        └── YYYY-MM-DD_Der-Aktionaer-E-Paper_##-2025.pdf
```

### Blob Verification

- [ ] Blobs created in correct year folders
- [ ] Publication ID folder naming correct
- [ ] File sizes match originals
- [ ] Content type: `application/pdf`
- [ ] Access tier: Cool

**Blob Metadata Check:**

- [ ] `publication_id`: correct
- [ ] `publication_date`: YYYY-MM-DD format
- [ ] `archived_at`: timestamp present

**PowerShell Verification:**

```powershell
# List blobs in container
az storage blob list \
  --account-name depotbutlerarchive \
  --container-name editions \
  --prefix "2025/" \
  --output table
```

---

## 6. MongoDB Tracking

### Processed Editions Collection

**Connect to MongoDB:**

```powershell
# Using mongosh or MongoDB Compass
mongosh "mongodb+srv://[cluster-url]" --username [user]
use depotbutler
db.processed_editions.find().sort({processed_at: -1}).limit(5).pretty()
```

**Verify Each Edition Entry:**

- [ ] Edition key format: `YYYY-MM-DD_publication-id`
- [ ] `publication_id`: matches processed publication
- [ ] `date`: YYYY-MM-DD
- [ ] `issue`: correct issue number
- [ ] `processed_at`: recent timestamp
- [ ] `file_path`: temp file path (or null if cleaned up)
- [ ] `downloaded_at`: timestamp present
- [ ] `email_sent_at`: timestamp present
- [ ] `onedrive_uploaded_at`: timestamp present
- [ ] `blob_archived`: true
- [ ] `blob_url`: valid Azure blob URL
- [ ] `blob_path`: correct path format
- [ ] `blob_container`: "editions"
- [ ] `file_size_bytes`: reasonable size

**Expected Document Structure:**

```json
{
  "_id": "2025-12-XX_megatrend-folger",
  "publication_id": "megatrend-folger",
  "date": "2025-12-XX",
  "issue": "XX/2025",
  "processed_at": ISODate("2025-12-XX..."),
  "file_path": null,
  "downloaded_at": ISODate("2025-12-XX..."),
  "email_sent_at": ISODate("2025-12-XX..."),
  "onedrive_uploaded_at": ISODate("2025-12-XX..."),
  "blob_archived": true,
  "blob_url": "https://depotbutlerarchive.blob.core.windows.net/...",
  "blob_path": "2025/megatrend-folger/...",
  "blob_container": "editions",
  "file_size_bytes": "699000"
}
```

### Publications Collection

- [ ] Active publications count: 2 (or more)
- [ ] `email_enabled`: true for Megatrend
- [ ] `onedrive_enabled`: true for both
- [ ] `subscription_id`: present for each
- [ ] Last processed dates updated

---

## 7. Admin Notifications

### Success Notification Email

- [ ] Received success notification email
- [ ] Subject: "✅ DepotButler - Erfolgreiche Verarbeitung"
- [ ] Lists all processed publications
- [ ] Shows recipient count for each
- [ ] OneDrive links included
- [ ] Blob archival status shown (✓ Archiviert)

**Success Email Content Check:**

- [ ] Greeting: "Hallo Stefan,"
- [ ] Summary section with publication count
- [ ] Per-publication details (title, issue, recipients, OneDrive link)
- [ ] Archival status with checkmark
- [ ] Professional formatting

### Error Notification (if any occurred)

- [ ] Received error notification (if errors occurred)
- [ ] Subject: "❌ DepotButler - Fehler bei der Verarbeitung"
- [ ] Error details included
- [ ] Publication name mentioned
- [ ] Error type identified

---

## 8. Sprint 5 Features Validation

### Blob Archival (Phase 5.3)

- [ ] ✅ Non-blocking archival working
- [ ] ✅ Editions archived even if email/OneDrive fails
- [ ] ✅ Blob metadata stored in MongoDB
- [ ] ✅ Blob URLs accessible

### Timestamp Tracking (Phase 5.2)

- [ ] ✅ `downloaded_at` captured
- [ ] ✅ `email_sent_at` captured
- [ ] ✅ `onedrive_uploaded_at` captured
- [ ] ✅ All timestamps in ISO format

### Notification System (Phase 5.5)

- [ ] ✅ Success emails sent to admins
- [ ] ✅ Archival status in notifications
- [ ] ✅ Multi-publication consolidated report

### Volume Mount (Sprint 5 Bonus)

- [ ] ✅ Temp files stored in `/mnt/data/tmp/`
- [ ] ✅ Volume mount persists across runs
- [ ] ✅ No disk space issues

---

## 9. Performance Metrics

### Execution Time

- [ ] Total workflow duration: ____________ seconds
- [ ] Time per publication: ____________ seconds average
- [ ] Download time: ____________ seconds per PDF
- [ ] Email send time: ____________ seconds per recipient
- [ ] OneDrive upload time: ____________ seconds per file
- [ ] Blob archival time: ____________ seconds per file

**Acceptable Ranges:**

- Total workflow: 30-120 seconds (depending on publication count)
- Per publication: 15-60 seconds
- Download: 5-30 seconds (network dependent)
- Email: 2-5 seconds per recipient
- OneDrive: 10-30 seconds (depends on file size)
- Blob archival: 5-15 seconds

### Resource Usage

- [ ] Memory usage stayed within 2.0Gi limit
- [ ] CPU usage reasonable (1.0 CPU allocated)
- [ ] No OOM (out of memory) errors
- [ ] No timeout errors

---

## 10. Issue Tracking

### Problems Encountered

| Issue | Severity | Description | Resolution |
| ----- | -------- | ----------- | ---------- |
| ☐ | High/Med/Low | | |
| ☐ | High/Med/Low | | |

### Follow-Up Actions Needed

- [ ] None - everything worked perfectly! 🎉
- [ ] _________________________
- [ ] _________________________

---

## 11. Production Readiness Assessment

### Critical Features ✅

- [ ] ✅ Authentication working
- [ ] ✅ Edition discovery working
- [ ] ✅ PDF download working
- [ ] ✅ Email delivery working
- [ ] ✅ OneDrive upload working
- [ ] ✅ Blob archival working
- [ ] ✅ MongoDB tracking working
- [ ] ✅ Volume mount working
- [ ] ✅ Admin notifications working

### Sprint 5 Status

- [ ] **Sprint 5 Complete**: 100% (all features working)
- [ ] **Production Ready**: YES / NO
- [ ] **Next Scheduled Run**: Monday, December 30, 2025 at 3:00 PM UTC

---

## 12. Sign-Off

**Verified By**: _______________________
**Date**: _______________________
**Status**: ☐ PASS ☐ FAIL ☐ PASS WITH NOTES

**Notes:**

```text
[Add any observations, improvements, or issues here]
```

---

## Quick Verification Commands

### Check Last Job Execution

```powershell
az containerapp job execution list \
  --name depot-butler-job \
  --resource-group depot-butler-rg \
  --output table
```

### View Job Logs

```powershell
az containerapp job logs show \
  --name depot-butler-job \
  --resource-group depot-butler-rg
```

### List Blobs Archived Today

```powershell
az storage blob list \
  --account-name depotbutlerarchive \
  --container-name editions \
  --prefix "2025/" \
  --output table
```

### Check MongoDB Recent Editions

```javascript
// In mongosh
use depotbutler
db.processed_editions.find(
  { processed_at: { $gte: new Date(new Date().setHours(0,0,0,0)) } }
).sort({ processed_at: -1 })
```

---

**Last Updated**: December 28, 2025
