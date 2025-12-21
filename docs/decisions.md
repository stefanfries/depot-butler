# Design Decisions (ADR-Light)

## ADR-001: Recipient-Specific Publication Preferences

**Status:** Proposed
**Date:** 2024-12-14
**Deciders:** System Architect

### Context

Currently, recipients receive all active publications via email. We need to allow recipients to:

1. Select which publications they want to receive
2. Choose delivery method per publication (email and/or OneDrive upload)
3. Customize OneDrive folder per recipient (optional)

### Decision

#### 1. Data Model Extension

Add `publication_preferences` field to `recipients` collection:

```javascript
{
  "_id": ObjectId("..."),
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "active": true,

  // NEW: Per-publication preferences
  "publication_preferences": [
    {
      "publication_id": "megatrend-folger",
      "enabled": true,
      "email_enabled": true,
      "upload_enabled": true,
      "custom_onedrive_folder": null  // Optional override
    },
    {
      "publication_id": "der-aktionaer-epaper",
      "enabled": true,
      "email_enabled": false,  // Disabled (file too large)
      "upload_enabled": true,
      "custom_onedrive_folder": "/personal/magazine"
    }
  ],

  "last_sent_at": ISODate("2024-12-14T08:00:00Z"),
  "send_count": 42
}
```

#### 2. Preference Resolution Rules

**Precedence (highest to lowest):**

1. Recipient's `publication_preferences` is **empty** → Skip recipient (no deliveries)
2. Recipient's `publication_preferences.enabled = false` → Skip recipient for that publication
3. Recipient's `publication_preferences.delivery_methods` → Use specified methods
4. Publication's global `email_enabled` / `onedrive_enabled` → Default options

**Validation Rules:**

- Recipient can only select delivery methods that are globally enabled for the publication
- If publication has `email_enabled: false`, recipient cannot choose email
- Empty `delivery_methods` = publication disabled for that recipient

#### 3. Explicit Opt-In Model

**Default Behavior:**

- Recipients with **empty** `publication_preferences: []`: **Receive NOTHING** (must explicitly opt-in)
- Recipients must have explicit preferences to receive publications
- This ensures intentional delivery and prevents unwanted emails

**Migration Strategy:**

- New recipients start with empty array = no deliveries until configured
- Existing recipients need preferences added explicitly
- This is an **opt-in model** by design

#### 4. OneDrive Folder Resolution

For upload delivery:

1. If `custom_onedrive_folder` is set → Use it
2. Otherwise → Use publication's `default_onedrive_folder`
3. Apply `organize_by_year` setting from publication

### Consequences

**Positive:**

- Flexible recipient control
- Gradual opt-in approach
- Reduces unwanted emails
- Supports large file handling (upload-only)

**Negative:**

- More complex query logic
- Larger recipient documents
- Need to maintain preferences UI/script

**Neutral:**

- Requires migration script for existing recipients (optional)

---

## ADR-002: Auto-Discovery and Synchronization of Publications

**Status:** Proposed
**Date:** 2024-12-14
**Deciders:** System Architect

### Context (ADR-002)

Currently, publications are manually configured in `publications.py` and seeded via script. We need automatic detection and synchronization with boersenmedien.com account.

### Decision (ADR-002)

#### 1. Discovery Flow

```text
1. Login to boersenmedien.com
2. Call discover_subscriptions() [already implemented]
3. Query MongoDB for existing publications
4. Compare discovered vs. existing:
   - New subscriptions → Create publication records (active=false by default)
   - Existing subscriptions → Update metadata (name, duration, etc.)
   - Missing subscriptions → Mark as inactive (don't delete)
5. Log changes for audit
```

#### 2. Publication Lifecycle States

```javascript
{
  "publication_id": "megatrend-folger",
  "active": true,          // Manually controlled - enables processing
  "discovered": true,      // Auto-detected from account
  "last_seen": ISODate("2024-12-14T10:00:00Z"),
  "first_discovered": ISODate("2024-01-01T10:00:00Z")
}
```

**State Transitions:**

- **New subscription detected** → `discovered: true, active: false` (requires manual activation)
- **Subscription still present** → Update `last_seen`
- **Subscription missing** → `discovered: false` (soft delete, keep history)

#### 3. Publication Identity

**Primary Key:** `publication_id` (manually assigned, stable)
**Discovery Match:** `subscription_id` from boersenmedien.com

**Mapping Strategy:**

- Maintain `PUBLICATION_SUBSCRIPTION_MAP` for stable IDs
- Admin can map discovered subscriptions to publication IDs
- Unmapped subscriptions get auto-generated IDs (e.g., `sub-2477462`)

#### 4. Metadata Synchronization

**Auto-Updated Fields:**

- `name` (from subscription)
- `subscription_number`
- `subscription_type`
- `duration`, `duration_start`, `duration_end`
- `last_seen`

**Manually Configured (Never Auto-Updated):**

- `publication_id`
- `active`
- `email_enabled`, `onedrive_enabled`
- `default_onedrive_folder`
- `organize_by_year`

#### 5. Discovery Frequency

**Option A (Recommended):** Every workflow run

- Pro: Always up-to-date
- Con: Extra HTTP request per run

**Option B:** Scheduled separate task

- Pro: Decoupled from workflow
- Con: Potential staleness

**Decision:** Option A - Run discovery at workflow start

### Consequences (ADR-002)

**Positive:**

- No manual publication management
- Always in sync with account
- Automatic detection of expired subscriptions
- Audit trail via `last_seen` timestamps

**Negative:**

- Additional HTTP requests
- Requires careful identity mapping
- Need admin UI to activate new publications

**Neutral:**

- Still requires manual configuration for delivery settings

---

## ADR-003: Multi-Publication Processing in Single Workflow Run

**Status:** Proposed
**Date:** 2024-12-14
**Deciders:** System Architect

### Context (ADR-003)

Currently, the workflow processes only the first active publication per run. We need to process all active publications in a single execution.

### Decision (ADR-003)

#### 1. Processing Strategy

**Sequential Processing (Recommended):**

```python
async def run_full_workflow(self):
    publications = await get_publications(active_only=True)

    results = []
    for publication in publications:
        try:
            result = await self._process_single_publication(publication)
            results.append(result)
        except Exception as e:
            # Log and continue with next publication
            logger.error(f"Failed to process {publication['name']}: {e}")
            results.append({"success": False, "error": str(e)})

    return {"results": results, "total": len(results)}
```

**Alternatives Considered:**

- **Parallel Processing:** Risk of overwhelming email server / OneDrive API
- **Separate Container Runs:** More complex orchestration

**Decision:** Sequential processing with continue-on-error

#### 2. Error Handling

**Per-Publication:**

- Log errors
- Send notification to admin
- Continue with next publication
- Track failures in workflow result

**Workflow-Level:**

- Success if at least one publication processed
- Return detailed results for all publications

#### 3. Edition Tracking

**Key Format:** `{publication_date}_{publication_id}`

- Already supports multiple publications
- Separate tracking per publication
- No changes needed

#### 4. Notification Strategy

**Success Notification:**

- Single summary email for all processed publications
- List each publication with status and OneDrive link

**Error Notification:**

- Immediate notification per failed publication
- Include exception details for troubleshooting

### Consequences (ADR-003)

**Positive:**

- Complete automation (all publications in one run)
- Simpler scheduling (single container job)
- Predictable resource usage
- Clear error reporting

**Negative:**

- Longer execution time
- One failure doesn't stop others (may be unexpected)

**Neutral:**

- Requires refactoring of current workflow structure
- May need rate limiting for email/OneDrive

---

## ADR-004: Publication Registry Migration from Code to Database

**Status:** Proposed
**Date:** 2024-12-14
**Deciders:** System Architect

### Context (ADR-004)

`publications.py` contains hardcoded `PUBLICATIONS` list. This should move to MongoDB to enable dynamic configuration.

### Decision (ADR-004)

#### 1. Migration Path

**Phase 1 (Backward Compatible):**

- Keep `publications.py` as fallback
- Prefer MongoDB if available
- Seed script populates MongoDB

**Phase 2 (Full Migration):**

- Remove `publications.py` registry
- All configuration in MongoDB
- Admin UI for management

**Decision:** Implement Phase 1 now, Phase 2 later

#### 2. Configuration Location

**MongoDB (Primary):**

```python
publications = await get_publications(active_only=True)
```

**Code Fallback (Deprecated):**

```python
from depotbutler.publications import PUBLICATIONS
```

#### 3. Access Pattern

**New API:**

```python
# Get all active
publications = await get_publications(active_only=True)

# Get specific
publication = await get_publication("megatrend-folger")

# Update
await update_publication("megatrend-folger", {"active": False})
```

#### 4. Seed Script Enhancement

`scripts/seed_publications.py`:

- Discover subscriptions
- Create/update publications
- Preserve manual settings
- Log changes

### Consequences (ADR-004)

**Positive:**

- Runtime configuration changes
- No code deployment for new publications
- Better separation of code and data
- Enables admin UI

**Negative:**

- Database becomes critical dependency
- Requires migration script
- More complex initialization

**Neutral:**

- Backward compatibility maintained during transition

---

## ADR-005: Recipient Delivery Logic

**Status:** Proposed
**Date:** 2024-12-14
**Deciders:** System Architect

### Context (ADR-005)

Need to determine who receives which publication via which method.

### Decision (ADR-005)

#### 1. Query Logic

```python
async def get_recipients_for_publication(
    publication_id: str,
    delivery_method: str  # "email" or "upload"
) -> list[dict]:
    """Get recipients who should receive this publication via this method."""

    # Get publication configuration
    publication = await get_publication(publication_id)

    # Check if delivery method is globally enabled
    if delivery_method == "email" and not publication.get("email_enabled", True):
        return []
    if delivery_method == "upload" and not publication.get("onedrive_enabled", True):
        return []

    # Determine which flag to check
    flag_name = "email_enabled" if delivery_method == "email" else "upload_enabled"

    # Query recipients
    recipients = await mongodb.db.recipients.find({
        "active": True,
        "$or": [
            # Case 1: No preferences = receive all enabled methods
            {"publication_preferences": {"$exists": False}},

            # Case 2: Publication explicitly enabled with this method
            {
                "publication_preferences": {
                    "$elemMatch": {
                        "publication_id": publication_id,
                        "enabled": True,
                        flag_name: True
                    }
                }
            }
        ]
    }).to_list(None)

    return recipients
```

#### 2. Processing Flow

```python
# For each publication
for publication in publications:
    # Process email delivery
    if publication["email_enabled"]:
        recipients = await get_recipients_for_publication(publication["publication_id"], "email")
        for recipient in recipients:
            await send_email(recipient, edition)

    # Process OneDrive upload
    if publication["onedrive_enabled"]:
        recipients = await get_recipients_for_publication(publication["publication_id"], "upload")
        for recipient in recipients:
            folder = get_onedrive_folder(recipient, publication)
            await upload_to_onedrive(edition, folder)
```

#### 3. Folder Resolution

```python
def get_onedrive_folder(recipient: dict, publication: dict) -> str:
    # Check for recipient-specific override
    for pref in recipient.get("publication_preferences", []):
        if pref["publication_id"] == publication["publication_id"]:
            if pref.get("custom_onedrive_folder"):
                return pref["custom_onedrive_folder"]

    # Use publication default
    return publication["default_onedrive_folder"]
```

### Consequences (ADR-005)

**Positive:**

- Clear precedence rules
- Flexible recipient control
- Efficient database queries
- Supports opt-in/opt-out

**Negative:**

- Complex query logic
- Need to test edge cases

**Neutral:**

- Requires MongoDB indexes for performance
