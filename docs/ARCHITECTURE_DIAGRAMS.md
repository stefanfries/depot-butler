# DepotButler Architecture Diagrams

## System Overview

```mermaid
graph TB
    subgraph "External Services"
        WEB[boersenmedien.com]
        ONEDRIVE[OneDrive/SharePoint]
        SMTP[GMX SMTP Server]
    end

    subgraph "Azure Container Apps"
        JOB[Scheduled Job<br/>Daily at 16:00 CET]
        APP[DepotButler<br/>Python Application]
        JOB --> APP
    end

    subgraph "Data Storage"
        MONGO[(MongoDB Atlas<br/>Publications, Recipients,<br/>Config, Metrics)]
        BLOB[Azure Blob Storage<br/>PDF Cache]
    end

    APP -->|Download PDFs| WEB
    APP -->|Store metadata| MONGO
    APP -->|Cache PDFs| BLOB
    APP -->|Upload PDFs| ONEDRIVE
    APP -->|Send emails| SMTP
    APP -->|Read config| MONGO

    style APP fill:#4CAF50
    style MONGO fill:#00897B
    style BLOB fill:#1976D2
```

## Clean Architecture Layers

```mermaid
graph LR
    subgraph "Domain Layer"
        MODELS[Pydantic Models<br/>Edition, Subscription,<br/>Publication]
    end

    subgraph "Application Layer"
        WORKFLOW[Workflow Orchestrator]
        DISCOVERY[Publication Discovery]
        TRACKING[Edition Tracking]
        PROCESSING[Publication Processing]
        NOTIFICATION[Notification Service]
    end

    subgraph "Infrastructure Layer"
        HTTP[HTTP Client<br/>httpx]
        DB[MongoDB Service<br/>motor]
        ONEDRIVE_SVC[OneDrive Service<br/>Graph API]
        EMAIL[Email Service<br/>SMTP]
        BLOB_SVC[Blob Storage Service]
    end

    WORKFLOW --> DISCOVERY
    WORKFLOW --> TRACKING
    WORKFLOW --> PROCESSING
    WORKFLOW --> NOTIFICATION

    DISCOVERY --> HTTP
    DISCOVERY --> DB

    TRACKING --> DB

    PROCESSING --> HTTP
    PROCESSING --> DB
    PROCESSING --> EMAIL
    PROCESSING --> ONEDRIVE_SVC
    PROCESSING --> BLOB_SVC

    NOTIFICATION --> EMAIL

    style MODELS fill:#FFA726
    style WORKFLOW fill:#66BB6A
    style HTTP fill:#42A5F5
    style DB fill:#26C6DA
```

## Workflow Execution Flow

```mermaid
sequenceDiagram
    participant Scheduler as Azure Scheduler
    participant Workflow as Workflow Orchestrator
    participant Discovery as Discovery Service
    participant DB as MongoDB
    participant Web as boersenmedien.com
    participant Tracking as Edition Tracker
    participant Processing as Processing Service
    participant Blob as Azure Blob Storage
    participant Email as Email Service
    participant OneDrive as OneDrive API

    Scheduler->>Workflow: Trigger (16:00 CET)

    Workflow->>Web: Login with cookie
    Web-->>Workflow: Authenticated

    Workflow->>Discovery: Sync publications
    Discovery->>Web: Discover subscriptions
    Web-->>Discovery: Subscription list
    Discovery->>DB: Update publications

    Workflow->>DB: Get active publications
    DB-->>Workflow: Publication list

    loop For each publication
        Workflow->>Processing: Process publication
        Processing->>Web: Get latest edition
        Web-->>Processing: Edition metadata

        Processing->>Tracking: Check if processed
        Tracking->>DB: Query processed_editions
        DB-->>Tracking: Not processed

        Processing->>Web: Download PDF
        Web-->>Processing: PDF bytes

        Processing->>Blob: Cache PDF
        Blob-->>Processing: Stored

        Processing->>DB: Get recipients
        DB-->>Processing: Recipient list

        opt Email enabled
            Processing->>Email: Send emails
            Email-->>Processing: Sent
        end

        opt Upload enabled
            Processing->>OneDrive: Upload to folders
            OneDrive-->>Processing: Uploaded
        end

        Processing->>Tracking: Mark processed
        Tracking->>DB: Insert record

        Processing-->>Workflow: Success
    end

    Workflow->>Email: Send admin summary
    Workflow->>DB: Save metrics
```

## Data Model Relationships

```mermaid
erDiagram
    PUBLICATIONS ||--o{ RECIPIENTS : "subscribed_by"
    PUBLICATIONS ||--o{ PROCESSED_EDITIONS : "has"
    RECIPIENTS ||--o{ PUBLICATION_PREFERENCES : "has"
    PROCESSED_EDITIONS ||--|| PUBLICATIONS : "references"
    METRICS ||--o{ PUBLICATION_METRICS : "contains"

    PUBLICATIONS {
        string publication_id PK
        string name
        string type
        bool active
        date duration_start
        date duration_end
        bool email_enabled
        bool onedrive_enabled
    }

    RECIPIENTS {
        string email PK
        string first_name
        string last_name
        bool active
        int send_count
        datetime last_sent_at
        array publication_preferences
    }

    PUBLICATION_PREFERENCES {
        string publication_id FK
        bool enabled
        bool email_enabled
        bool upload_enabled
        string custom_onedrive_folder
        bool organize_by_year
    }

    PROCESSED_EDITIONS {
        string _id PK
        string publication_id FK
        date date
        string title
        string issue
        datetime processed_at
        string blob_url
    }

    METRICS {
        string run_id PK
        datetime timestamp
        string status
        int total_publications
        array publication_metrics
    }
```

## Authentication & Security Flow

```mermaid
sequenceDiagram
    participant App as DepotButler
    participant DB as MongoDB Config
    participant Web as boersenmedien.com
    participant Admin as Admin Email

    App->>DB: Get auth cookie
    DB-->>App: Cookie + expiry date

    alt Cookie valid (>3 days)
        App->>Web: Use cookie
        Web-->>App: Authenticated ✓
    else Cookie expiring soon (<3 days)
        App->>Admin: Warning: Cookie expires in X days
        App->>Web: Use cookie
        Web-->>App: Authenticated ✓
    else Cookie expired
        App->>Admin: ERROR: Cookie expired
        App->>App: Workflow fails
    end

    Note over App,DB: Cookie refresh: scripts/update_cookie_mongodb.py
    Note over App,DB: Expiry: Every ~2 weeks
```

## Publication Processing State Machine

```mermaid
stateDiagram-v2
    [*] --> Discovering: Start workflow

    Discovering --> Loading: Sync complete
    Loading --> Processing: Publications loaded

    Processing --> CheckProcessed: For each publication

    CheckProcessed --> AlreadyProcessed: Found in DB
    CheckProcessed --> Downloading: Not processed

    AlreadyProcessed --> Processing: Skip, next publication

    Downloading --> Caching: PDF downloaded
    Caching --> Distributing: PDF cached

    Distributing --> Emailing: If email enabled
    Distributing --> Uploading: If upload enabled
    Distributing --> Tracking: Direct (both disabled)

    Emailing --> Uploading: If upload enabled
    Emailing --> Tracking: If upload disabled

    Uploading --> Tracking: Distribution complete

    Tracking --> Processing: Mark processed, next

    Processing --> Notifying: All done
    Notifying --> [*]: Send admin summary
```

## OneDrive Upload Strategy

```mermaid
graph TD
    START[Start Upload] --> SIZE{File size?}

    SIZE -->|< 4MB| SIMPLE[Simple Upload<br/>Single PUT request]
    SIZE -->|≥ 4MB| CHUNKED[Chunked Upload<br/>10MB chunks]

    SIMPLE --> CREATE_SESSION[Create upload session]
    CREATE_SESSION --> UPLOAD[Upload file]
    UPLOAD --> SUCCESS

    CHUNKED --> CREATE_CHUNKED[Create upload session]
    CREATE_CHUNKED --> LOOP[For each 10MB chunk]
    LOOP --> SEND[Send chunk with range]
    SEND --> CHECK{All chunks sent?}
    CHECK -->|No| LOOP
    CHECK -->|Yes| SUCCESS[✓ Upload complete]

    UPLOAD --> ERROR{Error?}
    SEND --> ERROR
    ERROR -->|Timeout| RETRY{Retry < 3?}
    ERROR -->|Auth| FAIL[✗ Upload failed]
    ERROR -->|Other| FAIL

    RETRY -->|Yes| SEND
    RETRY -->|No| FAIL

    SUCCESS --> ORGANIZE{Organize by year?}
    ORGANIZE -->|Yes| YEAR_FOLDER["📁 /publications/2025/file.pdf"]
    ORGANIZE -->|No| BASE_FOLDER["📁 /publications/file.pdf"]

    YEAR_FOLDER --> END[Done]
    BASE_FOLDER --> END
    FAIL --> END
```

## Admin Script Ecosystem

```mermaid
graph TB
    subgraph "Recipient Management"
        CHECK[check_recipients.py<br/>View recipients]
        MANAGE[manage_recipient_preferences.py<br/>10 commands]
    end

    subgraph "Publication Management"
        SEED[seed_publications.py<br/>Initial setup]
        ADD_PREF[add_recipient_preferences.py<br/>Legacy tool]
    end

    subgraph "Authentication"
        UPDATE_COOKIE[update_cookie_mongodb.py<br/>Refresh cookie]
        CHECK_COOKIE[cookie_checker.py<br/>Check status]
    end

    subgraph "Setup & Maintenance"
        INIT[init_app_config.py<br/>Initialize DB]
        ONEDRIVE_SETUP[setup_onedrive_auth.py<br/>OAuth setup]
        DRY_RUN[test_dry_run.py<br/>Test workflow]
    end

    subgraph "Data"
        MONGODB[(MongoDB Atlas)]
        ONEDRIVE_API[OneDrive API]
    end

    CHECK --> MONGODB
    MANAGE --> MONGODB
    SEED --> MONGODB
    ADD_PREF --> MONGODB
    UPDATE_COOKIE --> MONGODB
    CHECK_COOKIE --> MONGODB
    INIT --> MONGODB
    ONEDRIVE_SETUP --> ONEDRIVE_API
    DRY_RUN --> MONGODB

    style CHECK fill:#81C784
    style MANAGE fill:#66BB6A
    style UPDATE_COOKIE fill:#FFA726
    style ONEDRIVE_SETUP fill:#42A5F5
```

## Error Handling & Monitoring

```mermaid
graph LR
    subgraph "Error Detection"
        WORKFLOW[Workflow Execution]
        COOKIE[Cookie Check]
        DISCOVERY[Discovery Errors]
        DOWNLOAD[Download Failures]
        UPLOAD[Upload Failures]
        EMAIL[Email Failures]
    end

    subgraph "Error Handling"
        TRANSIENT[Transient Errors<br/>Retry 3x]
        AUTH[Auth Errors<br/>Alert admin]
        CONFIG[Config Errors<br/>Fail fast]
    end

    subgraph "Monitoring"
        METRICS[Metrics Collection<br/>MongoDB]
        LOGS[Structured Logging<br/>Console]
        NOTIFICATIONS[Admin Notifications<br/>Email]
    end

    WORKFLOW --> METRICS
    COOKIE --> LOGS
    DISCOVERY --> LOGS
    DOWNLOAD --> TRANSIENT
    UPLOAD --> TRANSIENT
    EMAIL --> TRANSIENT

    TRANSIENT --> METRICS
    AUTH --> NOTIFICATIONS
    CONFIG --> NOTIFICATIONS

    METRICS --> NOTIFICATIONS
    LOGS --> NOTIFICATIONS

    style AUTH fill:#F44336
    style TRANSIENT fill:#FFA726
    style CONFIG fill:#F44336
    style NOTIFICATIONS fill:#2196F3
```

## Deployment Architecture

```mermaid
graph TB
    subgraph "Development"
        DEV_CODE[Local Development<br/>VS Code + uv]
        TESTS[pytest suite<br/>437 tests]
        PRECOMMIT[Pre-commit Hooks<br/>ruff, mypy]
    end

    subgraph "CI/CD"
        GITHUB[GitHub Repository]
        ACTIONS[GitHub Actions<br/>Run tests]
    end

    subgraph "Azure Production"
        ACR[Azure Container Registry<br/>Docker Image]
        ACA[Azure Container Apps<br/>Scheduled Job]
        SCHEDULE[Cron: 0 15 * * *<br/>16:00 CET]
    end

    subgraph "External Resources"
        MONGO_ATLAS[(MongoDB Atlas<br/>Free Tier)]
        BLOB_STORAGE[Azure Blob Storage<br/>Cool Tier]
    end

    DEV_CODE --> TESTS
    TESTS --> PRECOMMIT
    PRECOMMIT --> GITHUB

    GITHUB --> ACTIONS
    ACTIONS --> ACR

    ACR --> ACA
    SCHEDULE --> ACA

    ACA --> MONGO_ATLAS
    ACA --> BLOB_STORAGE

    style ACA fill:#4CAF50
    style MONGO_ATLAS fill:#00897B
    style BLOB_STORAGE fill:#1976D2
    style ACTIONS fill:#2088FF
```

---

## Diagram Legend

- **Green**: Active processes/services
- **Blue**: External services/APIs
- **Teal**: Database/storage
- **Orange**: Authentication/security
- **Red**: Errors/failures

## Related Documentation

- [architecture.md](architecture.md) - Detailed architecture description
- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment procedures
- [MONGODB.md](MONGODB.md) - Database schema details
- [CONFIGURATION.md](CONFIGURATION.md) - Configuration guide
