# Dry-Run Mode

## Overview

Dry-run mode allows you to test the complete DepotButler workflow **without** actually sending emails or uploading files to OneDrive. This is useful for:

- Testing new recipient configurations
- Verifying publication preferences
- Checking recipient filtering logic
- Validating the workflow before running in production

## Usage

### Method 1: Using the test script (recommended)

```powershell
python scripts/test_dry_run.py
```

### Method 2: Direct command line

```powershell
python -m depotbutler.main full --dry-run
# or shorter:
python -m depotbutler.main full -n
```

### Method 3: From Python code

```python
from depotbutler.workflow import DepotButlerWorkflow

async with DepotButlerWorkflow(dry_run=True) as workflow:
    result = await workflow.run_full_workflow()
```

## What Happens in Dry-Run Mode

### ✅ These actions ARE performed:
- MongoDB connection and data fetching
- Login to boersenmedien.com
- Discovering subscriptions
- Checking for new editions
- Downloading PDF files
- Querying recipients for each publication
- Resolving folder paths and settings per recipient
- Checking edition tracking (if enabled)

### ❌ These actions are NOT performed:
- Sending emails to recipients
- Uploading files to OneDrive
- Sending admin notifications (success/error emails)
- Updating recipient statistics (send_count, last_sent_at)

## Example Output

When dry-run mode is enabled, you'll see log messages like:

```
🧪 DRY-RUN MODE: No emails will be sent and no files will be uploaded
🧪 DRY-RUN: Would send email to recipients for publication_id=megatrend-folger
🧪 DRY-RUN: Would send to stefan.fries@example.com
🧪 DRY-RUN: Would upload to OneDrive folder='Dokumente/Banken/...', organize_by_year=True
🧪 DRY-RUN: Would upload for stefan.fries@example.com to folder='...', organize_by_year=True
🧪 DRY-RUN: Would send success notification for: Megatrend Folger 50/2025
```

## Testing with Already Processed Editions

If an edition was already processed and you want to test the full workflow including email/upload logic, you have two options:

### Option 1: Force reprocess using MongoDB

```javascript
// In MongoDB Compass or mongosh
db.processed_editions.deleteOne({
  "edition_key": "megatrend-folger:50:2025"
})
```

### Option 2: Temporarily disable tracking

```javascript
// In MongoDB Compass or mongosh
db.config.updateOne(
  { _id: "app_config" },
  { $set: { tracking_enabled: false } }
)
```

Don't forget to re-enable tracking afterwards:

```javascript
db.config.updateOne(
  { _id: "app_config" },
  { $set: { tracking_enabled: true } }
)
```

## Use Cases

### 1. Testing New Recipient Configurations

After adding a new recipient or modifying publication preferences:

```powershell
# Add/modify recipient in MongoDB
python scripts/test_dry_run.py
# Verify the recipient appears in the dry-run output
```

### 2. Validating Folder Path Resolution

Check that custom OneDrive folders are correctly resolved:

```powershell
python scripts/test_dry_run.py
# Look for "Would upload for <email> to folder='...'" messages
```

### 3. Testing Publication Filtering

Verify that recipients only receive publications they're subscribed to:

```powershell
python scripts/test_recipient_filtering.py  # First, check filtering logic
python scripts/test_dry_run.py              # Then, test full workflow
```

## Safety Features

- **Clear warnings**: Multiple log messages indicate dry-run mode is active
- **No side effects**: No emails sent, no files uploaded, no stats updated
- **Real data**: Uses actual MongoDB data and live API calls (except email/upload)
- **Idempotent**: Can be run multiple times without affecting production

## Limitations

- PDF files are still downloaded (but not uploaded)
- Edition tracking still marks editions as processed (unless disabled)
- Cookie expiration warnings are still logged
- Some API rate limits may apply (for boersenmedien.com calls)
