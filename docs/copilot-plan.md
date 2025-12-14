# Implementation Plan: Multi-Publication & Recipient Preferences

## Overview

This plan implements the three main objectives:

1. **Auto-discovery and synchronization** of publications from boersenmedien.com
2. **Recipient-specific preferences** for publication selection and delivery methods
3. **Multi-publication processing** in a single workflow run

## Current State Analysis

### ✅ Already Implemented

- MongoDB integration for publications, recipients, and tracking
- Auto-discovery of subscriptions from boersenmedien.com (`discover_subscriptions()`)
- Publication storage in MongoDB (`publications` collection)
- Recipient storage in MongoDB (`recipients` collection)
- Edition tracking to prevent duplicates
- Email and OneDrive delivery mechanisms
- Global publication settings (`email_enabled`, `onedrive_enabled`)

### ❌ Not Yet Implemented

- Recipient publication preferences (per-recipient, per-publication)
- Custom delivery method selection per recipient
- Processing multiple publications in one workflow run
- Automatic publication synchronization from discovery
- Recipient-specific OneDrive folders

### 🔶 Partially Implemented

- Publication registry (exists in MongoDB, but workflow only processes first one)
- Seed script (`seed_publications.py` - manual execution required)

## Implementation Phases

---

## Phase 1: Database Schema Extensions

**Estimated Effort:** 2-3 hours  
**Risk:** Low  

### 1.1 Extend Recipients Collection

**File:** New migration script `scripts/migrate_recipient_preferences.py`

**Tasks:**

- [ ] Create migration script to add `publication_preferences` field
- [ ] Default: Empty array (= receive all active publications)
- [ ] Add indexes for efficient querying

**Schema:**

```javascript
{
  "email": "user@example.com",
  "publication_preferences": [
    {
      "publication_id": "megatrend-folger",
      "enabled": true,
      "email_enabled": true,
      "upload_enabled": false,
      "custom_onedrive_folder": null,
      "organize_by_year": null,  // null = use publication default, true/false = override
      "send_count": 0,  // Track sends per publication
      "last_sent_at": null  // Track last send per publication
    }
  ]
}
```

**Implementation Steps:**

1. Create `scripts/migrate_recipient_preferences.py`
2. Add `publication_preferences: list[dict] = []` to any recipient models
3. Run migration on existing database
4. Add MongoDB index: `db.recipients.createIndex({"publication_preferences.publication_id": 1})`
5. **Note**: Migration should initialize per-publication tracking fields:
   - `organize_by_year: null` (use publication default)
   - `send_count: 0` (reset per publication)
   - `last_sent_at: null` (no sends yet for this publication)
6. **Migration consideration**: Existing global `send_count` and `last_sent_at` will be deprecated but kept for backward compatibility during transition

**Testing:**

- Unit test: Verify migration script
- Integration test: Query with preferences
- Verify new tracking fields are properly initialized

---

### 1.2 Extend Publications Collection

**File:** Extend `scripts/seed_publications.py`

**Tasks:**

- [ ] Add `discovered` field (bool)
- [ ] Add `last_seen` field (datetime)
- [ ] Add `first_discovered` field (datetime)

**Schema Update:**

```javascript
{
  "publication_id": "megatrend-folger",
  "active": true,
  "discovered": true,
  "last_seen": ISODate("2024-12-14T10:00:00Z"),
  "first_discovered": ISODate("2024-01-01T10:00:00Z")
}
```

**Implementation Steps:**

1. Update `seed_publications.py` to set new fields
2. Create `scripts/migrate_publications_discovery.py` for existing records
3. Add indexes for discovery queries

**Testing:**

- Verify migration on existing publications
- Test discovery workflow updates

---

## Phase 2: Publication Auto-Discovery & Sync

**Estimated Effort:** 4-5 hours  
**Risk:** Medium  

### 2.1 Create Discovery Synchronization Service

**File:** New `src/depotbutler/discovery.py`

**Tasks:**

- [ ] Create `PublicationDiscoveryService` class
- [ ] Implement `sync_publications_from_account()` method
- [ ] Handle new subscriptions (create as inactive)
- [ ] Handle existing subscriptions (update metadata)
- [ ] Handle missing subscriptions (mark as not discovered)
- [ ] Log all changes for audit

**Interface:**

```python
class PublicationDiscoveryService:
    async def sync_publications_from_account(
        self,
        subscriptions: list[Subscription]
    ) -> dict:
        """
        Synchronize publications with discovered subscriptions.
        
        Returns:
            {
                "new": ["pub-id-1"],
                "updated": ["pub-id-2"],
                "missing": ["pub-id-3"],
                "unchanged": ["pub-id-4"]
            }
        """
```

**Implementation Steps:**

1. Create `discovery.py` module
2. Implement comparison logic (subscription_id matching)
3. Create/update/deactivate publication records
4. Add logging for all changes
5. Return summary of changes

**Testing:**

- Mock subscriptions and test each scenario
- Verify metadata updates don't overwrite manual settings
- Test new subscription detection

---

### 2.2 Integrate Discovery into Workflow

**File:** `src/depotbutler/workflow.py`

**Tasks:**

- [ ] Add discovery sync before processing publications
- [ ] Make it optional via config flag
- [ ] Log sync results
- [ ] Continue on sync failure (log warning)

**Implementation Steps:**

1. Add `discovery_enabled` config to MongoDB `app_config`
2. Call sync at workflow start
3. Log summary of changes
4. Continue even if discovery fails

**Code Location:** In `run_full_workflow()`, after cookie check

**Testing:**

- Test with discovery enabled/disabled
- Test with discovery failure
- Verify workflow continues on sync error

---

## Phase 3: Recipient Preference Queries

**Estimated Effort:** 3-4 hours  
**Risk:** Medium  

### 3.1 Add Recipient Query Functions

**File:** `src/depotbutler/db/mongodb.py`

**Tasks:**

- [ ] Implement `get_recipients_for_publication()`
- [ ] Implement folder resolution logic
- [ ] Add validation for delivery methods
- [ ] Support backward compatibility (no preferences = all publications)

**New Functions:**

```python
async def get_recipients_for_publication(
    publication_id: str,
    delivery_method: str  # "email" or "upload"
) -> list[dict]:
    """Get recipients who have enabled this delivery method for the publication."""

async def get_onedrive_folder_for_recipient(
    recipient: dict,
    publication: dict
) -> str:
    """Resolve OneDrive folder with precedence rules."""
```

**Implementation Steps:**

1. Add functions to `MongoDBService` class
2. Implement MongoDB query with `$or` for preferences
3. Add preference validation logic
4. Create helper for folder resolution (custom_onedrive_folder and organize_by_year)
5. Add convenience wrappers
6. Update tracking to use per-publication `send_count` and `last_sent_at`

**Folder Resolution Logic:**

- Priority 1: Recipient's `custom_onedrive_folder` (if set)
- Priority 2: Publication's `default_onedrive_folder`
- `organize_by_year` resolution: Recipient preference → Publication default → `true`

**Tracking Updates:**

- Move from global `recipient.send_count` to `publication_preferences[].send_count`
- Move from global `recipient.last_sent_at` to `publication_preferences[].last_sent_at`
- Update `update_recipient_send_stats()` to accept `publication_id` parameter

**Testing:**

- Test with no preferences (default behavior)
- Test with preferences (opt-in/opt-out)
- Test email_enabled/upload_enabled filtering
- Test folder resolution priority (custom vs default)
- Test organize_by_year resolution (recipient override vs publication default)
- Test validation (recipient can't enable method if publication has it disabled)
- Test per-publication tracking (send_count, last_sent_at)

---

### 3.2 Update Mailer Service

**File:** `src/depotbutler/mailer.py`

**Tasks:**

- [ ] Modify `send_pdf_to_recipients()` to accept publication_id
- [ ] Use new query function to get filtered recipients
- [ ] Update logging to include publication context

**Changes:**

```python
async def send_pdf_to_recipients(
    self,
    pdf_path: str,
    edition: Edition,
    publication_id: str  # NEW parameter
) -> bool:
    """Send PDF to recipients subscribed to this publication via email."""
    recipients = await get_recipients_for_publication(
        publication_id=publication_id,
        delivery_method="email"
    )
    # ... rest of implementation
```

**Implementation Steps:**

1. Add `publication_id` parameter
2. Replace `get_active_recipients()` with new query
3. Update all call sites
4. Update logging

**Testing:**

- Test with filtered recipients
- Test with no matching recipients
- Verify backward compatibility

---

### 3.3 Update OneDrive Service

**File:** `src/depotbutler/onedrive.py`

**Tasks:**

- [ ] Add `upload_for_recipients()` method
- [ ] Iterate recipients with custom folders
- [ ] Use folder resolution logic
- [ ] Support multiple uploads per edition

**New Method:**

```python
async def upload_for_recipients(
    self,
    edition: Edition,
    publication: dict,
    local_path: str
) -> list[UploadResult]:
    """Upload to OneDrive for all subscribed recipients."""
    recipients = await get_recipients_for_publication(
        publication_id=publication["publication_id"],
        delivery_method="upload"
    )
    
    results = []
    for recipient in recipients:
        folder = await get_onedrive_folder_for_recipient(recipient, publication)
        result = await self.upload_file(local_path, edition, folder, ...)
        results.append(result)
    
    return results
```

**Implementation Steps:**

1. Read current `onedrive.py` to understand API
2. Add new method for multi-recipient uploads
3. Implement folder resolution
4. Handle upload errors per recipient
5. Return aggregated results

**Testing:**

- Test with multiple recipients and custom folders
- Test with upload failures
- Verify folder path resolution

---

## Phase 4: Multi-Publication Workflow

**Estimated Effort:** 5-6 hours  
**Risk:** Medium-High  

### 4.1 Refactor Workflow Structure

**File:** `src/depotbutler/workflow.py`

**Tasks:**

- [ ] Extract single publication processing to `_process_single_publication()`
- [ ] Modify `run_full_workflow()` to iterate all active publications
- [ ] Implement error handling (continue on failure)
- [ ] Aggregate results for all publications
- [ ] Update notifications (summary format)

**New Structure:**

```python
async def run_full_workflow(self) -> dict:
    """Process all active publications."""
    # Discover & sync publications (if enabled)
    await self._sync_publications()
    
    # Get all active publications
    publications = await get_publications(active_only=True)
    
    results = []
    for publication in publications:
        try:
            result = await self._process_single_publication(publication)
            results.append(result)
        except Exception as e:
            logger.error(f"Failed to process {publication['name']}: {e}")
            results.append({
                "publication_id": publication["publication_id"],
                "success": False,
                "error": str(e)
            })
    
    # Send summary notification
    await self._send_summary_notification(results)
    
    return {
        "success": all(r["success"] for r in results),
        "results": results
    }

async def _process_single_publication(
    self,
    publication: dict
) -> dict:
    """Process a single publication (current workflow logic)."""
    # Current workflow logic here
    # Returns result dict with success, edition, etc.
```

**Implementation Steps:**

1. Create `_process_single_publication()` with current workflow logic
2. Modify `run_full_workflow()` to loop over publications
3. Update `self.current_publication_data` handling
4. Implement continue-on-error logic
5. Aggregate results
6. Update return structure

**Testing:**

- Test with single publication (backward compatibility)
- Test with multiple publications
- Test with one failure (should continue)
- Test with all failures

---

### 4.2 Update Edition Retrieval

**File:** `src/depotbutler/workflow.py` (method `_get_latest_edition_info`)

**Tasks:**

- [ ] Accept `publication` parameter
- [ ] Remove "first publication" logic
- [ ] Update for multi-publication context

**Current Issue:** Method gets "first active publication" - needs to accept publication parameter

**Implementation Steps:**

1. Add `publication: dict` parameter to `_get_latest_edition_info()`
2. Remove internal publication query
3. Update all call sites
4. Update logging context

**Testing:**

- Verify edition retrieval for each publication
- Test with missing subscription (should handle gracefully)

---

### 4.3 Update Notification System

**File:** `src/depotbutler/mailer.py`

**Tasks:**

- [ ] Create `send_summary_notification()` for multiple publications
- [ ] Include table of results (publication, status, link)
- [ ] Update error notification to include publication context
- [ ] Keep backward compatibility for single publication

**New Method:**

```python
async def send_summary_notification(
    self,
    results: list[dict]
) -> bool:
    """Send summary of all processed publications."""
    # HTML table with:
    # - Publication name
    # - Status (success/failure)
    # - Edition title
    # - OneDrive link
    # - Error message (if any)
```

**Implementation Steps:**

1. Create HTML template for summary
2. Implement `send_summary_notification()`
3. Add per-publication error notifications (optional)
4. Update success notification (keep for backward compat)

**Testing:**

- Test with all successes
- Test with mixed results
- Test with all failures

---

## Phase 5: Management Scripts & Tools

**Estimated Effort:** 3-4 hours  
**Risk:** Low  

### 5.1 Recipient Preference Management Script

**File:** New `scripts/manage_recipient_preferences.py`

**Tasks:**

- [ ] List recipient preferences
- [ ] Add/update publication preference for recipient
- [ ] Remove publication preference
- [ ] Toggle email_enabled/upload_enabled flags
- [ ] Set custom OneDrive folder

**CLI Interface:**

```bash
# List preferences
uv run python scripts/manage_recipient_preferences.py list user@example.com

# Add/update preference
uv run python scripts/manage_recipient_preferences.py set \
    user@example.com \
    --publication megatrend-folger \
    --email-enabled true \
    --upload-enabled false \
    --folder /custom/folder

# Remove preference
uv run python scripts/manage_recipient_preferences.py remove \
    user@example.com \
    --publication megatrend-folger
```

**Implementation Steps:**

1. Create script with argparse
2. Implement CRUD operations on preferences
3. Add validation (check publication exists, methods allowed)
4. Add pretty-printing for list command
5. Add confirmation prompts for destructive operations

**Testing:**

- Test all CRUD operations
- Test validation
- Test error handling

---

### 5.2 Publication Discovery Script

**File:** New `scripts/discover_and_sync_publications.py`

**Tasks:**

- [ ] Standalone discovery execution
- [ ] Show diff before applying changes
- [ ] Optional dry-run mode
- [ ] Interactive approval for new publications

**CLI Interface:**

```bash
# Dry run
uv run python scripts/discover_and_sync_publications.py --dry-run

# Interactive
uv run python scripts/discover_and_sync_publications.py --interactive

# Auto-sync
uv run python scripts/discover_and_sync_publications.py --auto
```

**Implementation Steps:**

1. Create script
2. Add discovery service call
3. Show diff in readable format
4. Implement dry-run mode
5. Add interactive approval

**Testing:**

- Test dry-run mode
- Test auto-sync
- Test with no changes

---

### 5.3 Update Seed Publications Script

**File:** `scripts/seed_publications.py`

**Tasks:**

- [ ] Add discovery fields to seeding
- [ ] Support marking subscriptions as discovered
- [ ] Add option to auto-activate new publications (default: false)

**Implementation Steps:**

1. Update publication data structure
2. Set `discovered: true`, `last_seen: now()`
3. Add `--auto-activate` flag (default: false)
4. Update documentation

---

## Phase 6: Testing & Documentation

**Estimated Effort:** 4-5 hours  
**Risk:** Low  

### 6.1 Unit Tests

**Files:** `tests/test_*.py`

**New Test Files:**

- [ ] `tests/test_discovery.py` - Discovery service tests
- [ ] `tests/test_recipient_preferences.py` - Preference queries
- [ ] `tests/test_multi_publication_workflow.py` - Full workflow tests

**Tasks:**

- [ ] Test discovery synchronization logic
- [ ] Test recipient preference queries
- [ ] Test multi-publication workflow
- [ ] Test error handling (continue on failure)
- [ ] Test backward compatibility (no preferences)
- [ ] Update existing tests for new signatures

---

### 6.2 Integration Tests

**File:** `tests/test_workflow_integration.py` (extend existing)

**Tasks:**

- [ ] Test full workflow with multiple publications
- [ ] Test with recipient preferences
- [ ] Test delivery method filtering
- [ ] Test OneDrive folder resolution
- [ ] Test discovery integration

---

### 6.3 Documentation Updates

**Files:** Various docs

**Tasks:**

- [ ] Update `README.md` with new features
- [ ] Update `CONFIGURATION.md` with preference settings
- [ ] Update `MONGODB.md` with new schema
- [ ] Create `docs/RECIPIENT_PREFERENCES.md` guide
- [ ] Create `docs/PUBLICATION_DISCOVERY.md` guide
- [ ] Update API documentation (docstrings)

---

## Implementation Order

### Sprint 1: Foundation (Phases 1-2) ✅ COMPLETED

**Duration:** 1-2 days

1. ✅ **Phase 1.1** - Recipient schema extension (`scripts/migrate_recipient_preferences.py`)
2. ✅ **Phase 1.2** - Publication schema extension (`scripts/migrate_publications_discovery.py`)
3. ✅ **Phase 2.1** - Discovery service (`src/depotbutler/discovery.py`)
4. ✅ **Phase 2.2** - Integrate into workflow (`src/depotbutler/workflow.py`)

**Deliverable:** Auto-discovery working, schema ready for preferences ✅

**Completed:** December 14, 2025

---

### Sprint 2: Preferences (Phase 3) ✅ COMPLETED

**Duration:** 1-2 days

1. ✅ **Phase 3.1** - Recipient query functions (`src/depotbutler/db/mongodb.py`)
   - `get_recipients_for_publication()` - Filter by publication and delivery method
   - `get_onedrive_folder_for_recipient()` - Resolve custom folder paths
   - `get_organize_by_year_for_recipient()` - Resolve organize setting
   - `update_recipient_stats()` - Per-publication tracking with MongoDB $ operator
2. ✅ **Phase 3.2** - Update mailer service (`src/depotbutler/mailer.py`)
   - Added `publication_id` parameter to `send_pdf_to_recipients()`
   - Integrated recipient filtering by publication
3. ✅ **Phase 3.3** - Update OneDrive service (`src/depotbutler/onedrive.py`)
   - Created `upload_for_recipients()` for multi-recipient uploads
   - Per-recipient folder and organize_by_year resolution
4. ✅ **Testing** - Comprehensive test suite (`tests/test_recipient_preferences.py`)
   - 20 tests covering queries, resolution, tracking, edge cases
   - 176 total tests passing with 76% coverage
5. ✅ **Dry-Run Mode** - Safe testing without side effects
   - Added `--dry-run` flag to workflow
   - Created test scripts (`scripts/test_dry_run.py`, `scripts/test_recipient_filtering.py`)
   - Documentation (`docs/DRY_RUN_MODE.md`)

**Deliverable:** Recipient preferences working for single publication ✅

**Completed:** December 14, 2025

---

### Sprint 3: Multi-Publication (Phase 4)

**Duration:** 2 days

1. **Day 5 Morning:** Phase 4.1 - Refactor workflow structure
2. **Day 5 Afternoon:** Phase 4.2 - Update edition retrieval
3. **Day 6 Morning:** Phase 4.3 - Update notifications
4. **Day 6 Afternoon:** Integration testing

**Deliverable:** Multi-publication workflow working end-to-end

---

### Sprint 4: Tools & Polish (Phases 5-6)

**Duration:** 1-2 days

1. **Day 7 Morning:** Phase 5.1 - Preference management script
2. **Day 7 Afternoon:** Phase 5.2 - Discovery script
3. **Day 8 Morning:** Phase 6 - Testing
4. **Day 8 Afternoon:** Documentation

**Deliverable:** Complete feature with tools and docs

---

## Risk Mitigation

### High Risk Items

1. **Multi-publication workflow complexity**
   - **Risk:** Breaking existing single-publication workflow
   - **Mitigation:** Keep `_process_single_publication()` isolated, test thoroughly

2. **Recipient preference query performance**
   - **Risk:** Slow queries with large recipient base
   - **Mitigation:** Add MongoDB indexes, test with realistic data size

3. **OneDrive API rate limiting**
   - **Risk:** Multiple uploads may hit rate limits
   - **Mitigation:** Add retry logic, consider batching/throttling

### Medium Risk Items

1. **Discovery matching accuracy**
   - **Risk:** Wrong subscription mapped to publication
   - **Mitigation:** Use stable mapping, require manual activation

2. **Backward compatibility**
   - **Risk:** Breaking existing workflows/scripts
   - **Mitigation:** Default to old behavior, gradual migration

3. **Error handling in multi-publication mode**
   - **Risk:** Unclear which publication failed
   - **Mitigation:** Detailed logging, per-publication error notifications

---

## Rollback Plan

### If Phase 3 Fails (Preferences)

- Keep global recipient list
- Use publication-level settings only
- Revert database schema changes

### If Phase 4 Fails (Multi-publication)

- Revert to single publication processing
- Keep preference system for future
- Process publications in separate runs

### Database Rollback

- Keep migration scripts reversible
- Backup database before each phase
- Test rollback procedures

---

## Success Criteria

### Phase 1-2 (Discovery)

- [ ] Publications automatically discovered from account
- [ ] New subscriptions created as inactive
- [ ] Metadata synchronized on each run
- [ ] Audit log shows all changes

### Phase 3 (Preferences)

- [ ] Recipients can opt-in/opt-out per publication
- [ ] Delivery methods filtered correctly
- [ ] Custom OneDrive folders working
- [ ] Backward compatibility maintained

### Phase 4 (Multi-Publication)

- [ ] All active publications processed in one run
- [ ] Failures don't stop other publications
- [ ] Summary notification shows all results
- [ ] Performance acceptable (< 5 min for 10 publications)

### Phase 5-6 (Tools & Docs)

- [ ] Management scripts working and documented
- [ ] All tests passing
- [ ] Documentation complete and accurate
- [ ] Migration guide available

---

## Monitoring & Validation

### Key Metrics

- Discovery sync time
- Number of publications processed per run
- Recipient query performance
- Email delivery success rate per publication
- OneDrive upload success rate
- Workflow execution time

### Logs to Add

- Discovery changes (new/updated/missing publications)
- Recipient preference matches per publication
- Per-publication processing time
- Delivery method filtering results

### Validation Queries

```javascript
// Check preference coverage
db.recipients.aggregate([
  {$match: {active: true}},
  {$project: {
    email: 1,
    has_preferences: {$gt: [{$size: {$ifNull: ["$publication_preferences", []]}}, 0]}
  }}
])

// Check publication discovery status
db.publications.aggregate([
  {$group: {
    _id: "$discovered",
    count: {$sum: 1}
  }}
])

// Check delivery method distribution
db.recipients.aggregate([
  {$unwind: "$publication_preferences"},
  {$group: {
    _id: {
      email: "$publication_preferences.email_enabled",
      upload: "$publication_preferences.upload_enabled"
    },
    count: {$sum: 1}
  }}
])

// Check per-publication tracking (send counts)
db.recipients.aggregate([
  {$unwind: "$publication_preferences"},
  {$group: {
    _id: "$publication_preferences.publication_id",
    total_sends: {$sum: "$publication_preferences.send_count"},
    avg_sends: {$avg: "$publication_preferences.send_count"},
    recipients: {$sum: 1}
  }}
])

// Check organize_by_year overrides
db.recipients.aggregate([
  {$unwind: "$publication_preferences"},
  {$match: {"publication_preferences.organize_by_year": {$ne: null}}},
  {$group: {
    _id: {
      publication: "$publication_preferences.publication_id",
      organize_by_year: "$publication_preferences.organize_by_year"
    },
    count: {$sum: 1}
  }}
])
```

---

## Next Steps

1. **Review this plan** with stakeholders
2. **Prioritize phases** based on urgency
3. **Set up development branch** for implementation
4. **Create tickets** for each phase
5. **Begin Sprint 1** with Phase 1.1

---

## Open Questions

1. **How to handle large number of recipients per publication?**
   - Consider batching email sends?
   - Parallel processing with rate limiting?

2. **OneDrive folder structure for recipient-specific uploads?**
   - Separate folder per recipient?
   - Shared folder with subfolders?
   - Security/access control implications?

3. **Admin UI requirements?**
   - Web interface needed?

4. **Per-publication tracking migration strategy?**
   - Should we migrate historical `send_count` and `last_sent_at` to all publication preferences?
   - Or start fresh with per-publication tracking (all set to 0/null)?
   - Keep global fields during transition period for reporting?
   - CLI tools sufficient?
   - Auto-activation policy for new publications?

5. **Notification preferences?**
   - Should recipients also configure notification preferences?
   - Separate admin notifications per publication?

6. **Discovery conflict resolution?**
   - What if subscription ID changes?
   - How to handle renamed subscriptions?
   - Manual intervention required?

---

## Dependencies

### External Services

- MongoDB Atlas (database)
- boersenmedien.com (discovery API)
- OneDrive API (file upload)
- SMTP server (email delivery)

### Python Packages

- motor (async MongoDB)
- httpx (HTTP client)
- beautifulsoup4 (HTML parsing)
- pydantic (data validation)

### Configuration

- MongoDB connection string
- OneDrive OAuth tokens
- SMTP credentials
- Cookie authentication
