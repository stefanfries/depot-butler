# DepotButler Architecture

## Overview

DepotButler is a Python-based automation system that downloads financial publications from boersenmedien.com, processes them, and distributes them to recipients via email and/or OneDrive upload.

## Architectural Style

The system follows **Clean Architecture** principles with clear separation of concerns:

### Layers

1. **Domain Layer** (`models.py`)
   - Core business entities: `Edition`, `Subscription`, `UploadResult`
   - Pure data models with no external dependencies
   - Uses Pydantic for validation

2. **Infrastructure Layer**
   - **HTTP Client** (`httpx_client.py`): Web scraping and downloads using httpx
   - **Database** (`db/mongodb.py`): MongoDB operations using Motor (async driver)
   - **OneDrive Service** (`onedrive.py`): File upload operations
   - **Email Service** (`mailer.py`): SMTP email operations

3. **Application Layer**
   - **Workflow Orchestrator** (`workflow.py`): Main business logic coordination
   - **Edition Tracker** (`edition_tracker.py`): Duplicate detection using MongoDB
   - **Publications Manager** (`publications.py`): Publication configuration registry

4. **Utilities** (`utils/`)
   - Logging, helper functions, common utilities

## Current Data Model

### MongoDB Collections

#### 1. `publications` Collection

Stores metadata about available publications from boersenmedien.com.

```javascript
{
  "_id": ObjectId("..."),
  "publication_id": "megatrend-folger",  // Unique identifier
  "name": "Megatrend Folger",            // Display name
  "subscription_id": "2477462",           // From boersenmedien.com
  "subscription_number": "123456",        // From boersenmedien.com
  "subscription_type": "Jahresabo",       // Subscription type
  "duration": "02.07.2025 - 01.07.2026", // Duration string
  "duration_start": ISODate("2025-07-02T00:00:00Z"),
  "duration_end": ISODate("2026-07-01T00:00:00Z"),
  "active": true,                         // Enable/disable publication
  
  // Delivery settings (global per publication)
  "email_enabled": true,                  // Can be sent via email
  "onedrive_enabled": true,               // Can be uploaded to OneDrive
  
  // OneDrive configuration
  "default_onedrive_folder": "Dokumente/Banken/DerAktionaer/Strategie_800-Prozent",
  "organize_by_year": true,               // Create year subfolders
  
  "created_at": ISODate("2024-12-14T10:00:00Z"),
  "updated_at": ISODate("2024-12-14T10:00:00Z")
}
```

#### 2. `recipients` Collection

Stores recipient information and delivery preferences.

**Current Structure:**

```javascript
{
  "_id": ObjectId("..."),
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "active": true,
  "recipient_type": "subscriber",  // or "admin"
  "last_sent_at": ISODate("2024-12-14T08:00:00Z"),
  "send_count": 42
}
```

**Missing (To Be Implemented):**

- Per-publication preferences
- Delivery method preferences (email_enabled/upload_enabled per publication)
- Custom OneDrive folders per recipient

#### 3. `processed_editions` Collection

Tracks processed editions to prevent duplicates.

```javascript
{
  "_id": ObjectId("..."),
  "edition_key": "2024-12-01_megatrend-folger",
  "title": "Megatrend Folger #123",
  "publication_date": "2024-12-01",
  "download_url": "https://...",
  "file_path": "/tmp/megatrend-folger-2024-12-01.pdf",
  "processed_at": ISODate("2024-12-01T06:00:00Z")
}
```

#### 4. `config` Collection

Application configuration (key-value store).

```javascript
// Auth cookie document
{
  "_id": "auth_cookie",
  "cookie_value": "...",
  "expires_at": ISODate("2025-01-01T00:00:00Z"),
  "updated_at": ISODate("2024-12-14T10:00:00Z"),
  "updated_by": "admin"
}

// App config document
{
  "_id": "app_config",
  "tracking_enabled": true,
  "tracking_retention_days": 90,
  "cookie_warning_days": 5,
  "admin_emails": ["admin@example.com"]
}
```

## Current Workflow

### Main Processing Flow (`workflow.py`)

```text
1. Check cookie expiration (warning only)
2. Get latest edition info
   - Login with cookie authentication
   - Discover subscriptions from account
   - Get first active publication from MongoDB
   - Fetch latest edition
3. Check if already processed (skip if yes)
4. Download PDF
5. Send via email (if enabled for publication)
   - Get all active recipients
   - Send to each recipient
   - Update recipient statistics
6. Upload to OneDrive (if enabled for publication)
7. Mark as processed in tracking
8. Send success notification to admin
9. Cleanup temporary files
```

### Discovery Process (`httpx_client.py`)

The system can auto-discover subscriptions:

1. Login to boersenmedien.com
2. Scrape `/produkte/abonnements` page
3. Extract subscription metadata (ID, number, name, type, duration)
4. Build edition URLs

## Authentication

### Cookie-Based Authentication

- Uses `.AspNetCore.Cookies` from browser
- Stored in MongoDB `config` collection
- Expiration tracking with warnings
- Manual cookie refresh required (via `scripts/update_cookie_mongodb.py`)

## Key Architectural Decisions

### 1. MongoDB as Central Data Store

**Rationale:**

- Flexible schema for evolving requirements
- Built-in support for async operations (Motor)
- Easy to query and update recipient/publication preferences
- No complex joins needed

### 2. Async/Await Pattern

**Rationale:**

- Efficient I/O operations (HTTP, database, file operations)
- Non-blocking concurrent processing
- Better resource utilization in containerized environment

### 3. HTTPX over Playwright

**Rationale:**

- Lighter weight (no browser automation needed)
- Faster execution
- Lower resource requirements
- Sufficient for cookie-based authentication

### 4. Publication Registry Pattern

**Current:** Static list in `publications.py`
**Future:** Dynamic from MongoDB with auto-discovery

### 5. Edition Tracking

**Implementation:** MongoDB-based deduplication
**Key:** `{publication_date}_{publication_id}`
**Retention:** Configurable (default 90 days)

## Extension Points

### 1. Adding New Publications

Currently: Edit `publications.py` and `scripts/seed_publications.py`
Future: Auto-discovery and admin UI

### 2. Custom Recipient Logic

Currently: Global recipients for all publications
Future: Per-publication, per-recipient preferences

### 3. Delivery Methods

Currently: Email and OneDrive (fixed)
Future: Pluggable delivery strategies

## Deployment Architecture

### Container-Based (Azure Container Instance)

- Single-container deployment
- Scheduled execution via Azure Container Instance Jobs
- Environment variables for secrets
- MongoDB Atlas for data persistence
- OneDrive for file storage

## Security Considerations

1. **Secrets Management:** Environment variables or Azure Key Vault
2. **Cookie Storage:** Encrypted in MongoDB
3. **Authentication:** Cookie-based with expiration tracking
4. **Email:** SMTP credentials in environment
5. **OneDrive:** OAuth2 with refresh token

## Performance Characteristics

### Current Bottlenecks

1. Sequential recipient processing (email sending)
2. Single publication per run
3. Cookie manual refresh

### Scalability

- Designed for small-scale (< 100 recipients, < 10 publications)
- Can be parallelized per publication
- MongoDB can handle growth

## Testing Strategy

- Unit tests for individual components
- Integration tests for workflow
- Mock external dependencies (HTTP, SMTP, OneDrive)
- MongoDB test fixtures
