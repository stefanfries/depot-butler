# Sprint 3: Multi-Publication Support

**Status:** Ready to implement  
**Updated:** 2025-12-14  
**Breaking Change:** Yes - opt-in model now enforced

---

## Overview

Extend the workflow to process **all active publications** in a single job run, with explicit opt-in model for recipients.

### Key Changes from Original Plan

⚠️ **BREAKING CHANGE**: Changed default behavior for recipients without preferences:

- **OLD**: Empty `publication_preferences: []` = receive all publications
- **NEW**: Empty `publication_preferences: []` = receive **NOTHING** (must opt-in)

This ensures intentional delivery and prevents unwanted emails.

---

## Current State

- Workflow processes only the **first** active publication
- Recipients with empty preferences would receive everything (old behavior)
- Comment at workflow.py:280: `"Process first active publication (for now)"`

## Goals

1. ✅ Process **all** active publications in single job run
2. ✅ Enforce explicit opt-in model for recipients
3. ✅ Maintain individual tracking per publication
4. ✅ Handle partial failures gracefully
5. ✅ Provide consolidated notification

---

## Prerequisites (MUST DO BEFORE SPRINT 3)

### Critical: Add Recipient Preferences

Since we changed to opt-in model, **recipients need explicit preferences** or they'll receive nothing.

**Option 1: Manual Configuration** (Recommended for control)

```javascript
// MongoDB Shell or Compass
db.recipients.updateOne(
  { email: "user@example.com" },
  {
    $set: {
      publication_preferences: [
        {
          publication_id: "megatrend-folger",
          enabled: true,
          email_enabled: true,
          upload_enabled: true,
          send_count: 0,
          last_sent_at: null
        },
        {
          publication_id: "der-aktionaer-epaper", 
          enabled: true,
          email_enabled: true,
          upload_enabled: true,
          send_count: 0,
          last_sent_at: null
        }
      ]
    }
  }
)
```

**Option 2: Bulk Script** (if you want all recipients to receive both)

```python
# scripts/add_default_preferences.py (create this)
import asyncio
from depotbutler.db.mongodb import MongoDBService

async def add_default_preferences():
    async with MongoDBService() as db:
        # Get all active recipients without preferences
        recipients = await db.db.recipients.find({
            "active": True,
            "$or": [
                {"publication_preferences": {"$exists": False}},
                {"publication_preferences": {"$size": 0}}
            ]
        }).to_list(None)
        
        print(f"Found {len(recipients)} recipients needing preferences")
        
        default_prefs = [
            {
                "publication_id": "megatrend-folger",
                "enabled": True,
                "email_enabled": True,
                "upload_enabled": True,
                "send_count": 0,
                "last_sent_at": None
            },
            {
                "publication_id": "der-aktionaer-epaper",
                "enabled": True,
                "email_enabled": True,
                "upload_enabled": True,
                "send_count": 0,
                "last_sent_at": None
            }
        ]
        
        for recipient in recipients:
            await db.db.recipients.update_one(
                {"_id": recipient["_id"]},
                {"$set": {"publication_preferences": default_prefs}}
            )
            print(f"✓ Updated: {recipient['email']}")

asyncio.run(add_default_preferences())
```

**Verify Setup:**
```bash
# Check recipients have preferences
python scripts/test_recipient_filtering.py
```

---

## Task Breakdown

### Task 3.1: Extract Single Publication Processing

**Estimated: 2-3 hours**

Create reusable method for processing one publication:

```python
@dataclass
class PublicationResult:
    publication_id: str
    publication_name: str
    success: bool
    edition: Optional[Edition] = None
    already_processed: bool = False
    error: Optional[str] = None
    download_path: Optional[str] = None
    upload_result: Optional[UploadResult] = None
    recipients_emailed: int = 0
    recipients_uploaded: int = 0
```

- [ ] Add `PublicationResult` dataclass to workflow.py
- [ ] Create `async def _process_single_publication(self, publication_data: dict) -> PublicationResult`
- [ ] Move Steps 3-9 into this method
- [ ] Ensure `self.current_publication_data` is set correctly
- [ ] Return structured result

### Task 3.2: Implement Multi-Publication Loop

**Estimated: 1-2 hours**

Replace single publication logic with iteration:

- [ ] Modify `run()` to iterate all publications
- [ ] Add exception handling per publication
- [ ] Collect all results in list
- [ ] Log progress per publication

```python
# In run() method
publications = await get_publications(active_only=True)
if not publications:
    logger.warning("No active publications found")
    return

results = []
for pub_data in publications:
    try:
        logger.info(f"Processing {pub_data['name']}...")
        result = await self._process_single_publication(pub_data)
        results.append(result)
    except Exception as e:
        logger.error(f"Failed to process {pub_data['name']}: {e}")
        results.append(PublicationResult(
            publication_id=pub_data['publication_id'],
            publication_name=pub_data['name'],
            success=False,
            error=str(e)
        ))
```

### Task 3.3: Update Notification System
**Estimated: 2-3 hours**

Replace single-publication notification with summary:

- [ ] Create `async def _send_consolidated_notification(self, results: list[PublicationResult])`
- [ ] Format email with table of all publications
- [ ] Include success/failure counts
- [ ] Show recipient counts per publication
- [ ] Keep individual error notifications for critical failures

**Email Format:**
```
📊 DepotButler Daily Report
━━━━━━━━━━━━━━━━━━━━━━━━━

Processed: 2 publication(s)
✅ Success: 1 | ℹ️ Skipped: 1 | ❌ Failed: 0

━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Megatrend Folger 50/2025
   Published: 2025-12-11
   Recipients: 3 emailed, 3 uploaded
   OneDrive: [View File]

ℹ️ DER AKTIONÄR E-Paper 51/2025
   Status: Already processed (2025-12-09)

━━━━━━━━━━━━━━━━━━━━━━━━━
Total Runtime: 12.5s
```

### Task 3.4: Update Edition Tracking
**Estimated: 1 hour**

- [ ] Verify `edition_tracker` correctly tracks per publication_id
- [ ] Test multiple publications processed simultaneously
- [ ] Ensure no cross-contamination

### Task 3.5: Testing & Documentation
**Estimated: 2-3 hours**

- [ ] Write `test_process_single_publication()`
- [ ] Write `test_multi_publication_loop()`
- [ ] Write `test_consolidated_notification()`
- [ ] Test scenarios:
  - 2 new editions (both succeed)
  - 1 new + 1 already processed
  - 1 success + 1 failure
  - Both already processed
  - Both fail
  - No recipients have preferences for a publication
- [ ] Update [docs/architecture.md](architecture.md)
- [ ] Update [README.md](../README.md)

---

## Success Criteria

- ✅ Both publications processed in single run
- ✅ Recipients without preferences receive nothing (opt-in verified)
- ✅ If one publication fails, other completes
- ✅ Single consolidated email notification
- ✅ Individual tracking works per publication
- ✅ All 176+ tests pass
- ✅ Azure job handles multiple publications

---

## Risks & Mitigation

### Risk 1: No Recipients Have Preferences
**Impact:** Publications processed but nothing delivered  
**Mitigation:** 
- Add validation warning if no recipients found
- Include in notification: "No recipients configured for X"
- Provide clear setup instructions

### Risk 2: Runtime Doubles
**Impact:** May approach Azure job timeout (currently ~6s, could become 12-15s)  
**Mitigation:**
- Monitor Azure logs after deployment
- Publications processed sequentially (safer than parallel)
- Can add timeout handling if needed

### Risk 3: Storage Capacity
**Impact:** Two PDFs downloaded simultaneously  
**Mitigation:**
- Cleanup after each publication (not at end)
- Temp directory should handle 2x ~20MB files easily

---

## Migration Notes

### For Existing Users

1. **Add recipient preferences** before deploying Sprint 3
2. Test with `scripts/test_recipient_filtering.py`
3. Verify at least 1 recipient configured per publication
4. Deploy and monitor first run carefully

### Rollback Plan

If issues arise:
- Revert to commit before Sprint 3
- Recipient preferences remain (no data loss)
- Single-publication mode resumes

---

## Estimated Timeline

- **Total Time:** 8-12 hours
- **Sessions:** 2-3 coding sessions
- **Testing:** 2-3 hours included

---

## Questions Before Starting?

- How many recipients do you have currently?
- Should we create the bulk preference script first?
- Want to test with preferences on staging/local first?

