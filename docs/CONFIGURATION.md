# ⚙️ Configuration Guide

This guide explains how to configure depot-butler using both environment variables (.env) and MongoDB-based dynamic configuration.

---

## 📋 Configuration Architecture

**Last Updated**: December 29, 2025

Depot-butler uses a hybrid configuration approach:

### 🔐 Environment Variables (.env)

**Purpose**: Secrets, credentials, and bootstrap settings
**Location**: `.env` file (gitignored)
**When to use**: Settings that rarely change or contain sensitive data

### 🗄️ MongoDB Configuration

**Purpose**: Dynamic settings that change without redeployment
**Location**: `config` collection in MongoDB
**When to use**: Settings that need frequent updates or environment-specific values

---

## 🚀 Initial Setup

### 1. Configure Environment Variables

Copy the template and fill in your values:

```bash
cp .env.example .env
# Edit .env with your credentials
```

**Required .env settings:**

```bash
# MongoDB Connection (needed to access dynamic config)
DB_CONNECTION_STRING=mongodb+srv://...

# Credentials (secrets)
BOERSENMEDIEN_USERNAME=your.email@example.com
BOERSENMEDIEN_PASSWORD=your_password
ONEDRIVE_CLIENT_SECRET=your_secret
ONEDRIVE_REFRESH_TOKEN=your_token
SMTP_PASSWORD=your_smtp_password

# Fallback Admin Email
SMTP_ADMIN_ADDRESS=admin@example.com
```

### 2. Initialize MongoDB Configuration

Run the initialization script to create the `app_config` document:

```bash
$env:PYTHONPATH="src" ; uv run python scripts/init_app_config.py
```

This creates the MongoDB configuration with defaults from your `.env` file:

```javascript
{
  "_id": "app_config",
  "log_level": "INFO",
  "cookie_warning_days": 5,
  "admin_emails": ["admin@example.com"],  // from SMTP_ADMIN_ADDRESS

  // OneDrive settings (Note: folder paths are per-publication)
  "onedrive_organize_by_year": true,

  // Tracking settings
  "tracking_enabled": true,
  "tracking_retention_days": 90,

  // SMTP settings
  "smtp_server": "smtp.gmx.net",
  "smtp_port": 587
}
```

**Note**: OneDrive folder paths are configured per publication in the `publications` collection (`default_onedrive_folder`) and can be overridden per recipient in `publication_preferences` (`custom_onedrive_folder`).

---

## 🎛️ MongoDB Dynamic Configuration

### Available Settings

| Setting | Type | Default | Description |
| ------- | ---- | ------- | ----------- |
| `log_level` | String | `INFO` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `cookie_warning_days` | Number | `3` | Days before cookie expiration to send warning emails |
| `admin_emails` | Array | From .env | List of email addresses to receive admin notifications |
| `onedrive_organize_by_year` | Boolean | `true` | Organize files by year (creates YYYY subfolder) |
| `tracking_enabled` | Boolean | `true` | Enable/disable edition tracking |
| `tracking_retention_days` | Number | `90` | Days to keep tracking records |
| `smtp_server` | String | `smtp.gmx.net` | SMTP server hostname |
| `smtp_port` | Number | `587` | SMTP server port |

**Note**: OneDrive folder paths are NOT in `app_config`. They are configured:

- Per publication: `publications.default_onedrive_folder`
- Per recipient override: `publication_preferences.custom_onedrive_folder`

### How to Change Settings

#### Using MongoDB Compass (GUI)

1. Open MongoDB Compass and connect to your cluster
2. Navigate to `depotbutler` database → `config` collection
3. Find the document with `_id: "app_config"`
4. Click "Edit Document"
5. Modify values
6. Save changes

**Changes take effect on next workflow run!**

#### Using mongosh (CLI)

```javascript
// Connect to your cluster
mongosh "mongodb+srv://cluster0.xxxxx.mongodb.net/depotbutler"

// Change log level
db.config.updateOne(
  { _id: "app_config" },
  { $set: { log_level: "DEBUG" } }
)

// Adjust cookie warning threshold
db.config.updateOne(
  { _id: "app_config" },
  { $set: { cookie_warning_days: 7 } }
)

// Add admin email
db.config.updateOne(
  { _id: "app_config" },
  { $push: { admin_emails: "newadmin@example.com" } }
)

// Remove admin email
db.config.updateOne(
  { _id: "app_config" },
  { $pull: { admin_emails: "oldadmin@example.com" } }
)

// Change OneDrive folder path (per publication)
db.publications.updateOne(
  { publication_id: "megatrend-folger" },
  { $set: { default_onedrive_folder: "Dokumente/NewPath" } }
)

// Disable year-based organization
db.config.updateOne(
  { _id: "app_config" },
  { $set: { onedrive_organize_by_year: false } }
)

// Change tracking retention
db.config.updateOne(
  { _id: "app_config" },
  { $set: { tracking_retention_days: 120 } }
)

// Switch SMTP server
db.config.updateOne(
  { _id: "app_config" },
  { $set: {
    smtp_server: "smtp.gmail.com",
    smtp_port: 587
  } }
)

// View current configuration
db.config.findOne({ _id: "app_config" })
```

---

## 📖 Configuration Details

### Log Level

Controls logging verbosity for troubleshooting:

- **`DEBUG`**: Extremely verbose, shows all operations and data
- **`INFO`**: Normal operations (default)
- **`WARNING`**: Only warnings and errors
- **`ERROR`**: Only errors

**When to change:**

- Set to `DEBUG` when troubleshooting issues
- Keep at `INFO` for normal operations
- Use `WARNING` or `ERROR` in production to reduce noise

**Environment variable override:**

```bash
# In .env (optional)
LOG_LEVEL=DEBUG
```

The priority is: MongoDB config > Environment variable > Default (INFO)

### Cookie Warning Days

Number of days before cookie expiration to start sending warning emails.

**Default:** 3 days (updated December 2025)
**Recommended range:** 3-7 days
**Environment variable**: `NOTIFICATION_COOKIE_WARNING_DAYS`

**Example scenarios:**

- Set to `7` if you check emails infrequently
- Set to `3` for balanced warning frequency (default)
- Set to `1` for last-minute reminders only

**How warnings work:**

- Warning emails sent daily once threshold is reached
- Error email sent immediately when cookie expires
- Warnings continue until you update the cookie

### Admin Emails

List of email addresses that receive:

- Success notifications (edition downloaded and uploaded)
- Warning notifications (cookie expiring soon)
- Error notifications (failures, cookie expired)
- System alerts

**Features:**

- Supports multiple admin emails
- All admins receive same notifications
- Add/remove without redeployment
- Falls back to `SMTP_ADMIN_ADDRESS` from .env if MongoDB config missing

**Best practices:**

- Include at least one email you check regularly
- Add backup email in case primary is unavailable
- Remove old emails when team members leave

### OneDrive Settings

#### Base Folder Path

OneDrive directory where PDFs are uploaded.

**Default:** `/Dokumente/Banken/DerAktionaer/Strategie_800-Prozent`
**Format:** Absolute path from OneDrive root

**When to change:**

- Reorganizing folder structure
- Different storage location per environment
- Multiple publication types

#### Organize by Year

Whether to create year-based subfolders (YYYY).

**Default:** `true`
**Options:** `true` or `false`

**Behavior:**

- `true`: Files saved to `/base_path/2025/filename.pdf`
- `false`: Files saved to `/base_path/filename.pdf`

**Use cases:**

- `true`: Long-term archival with year organization
- `false`: Flat structure, easier to browse

### Tracking Settings

#### Tracking Enabled

Enable/disable edition duplicate checking.

**Default:** `true`
**Options:** `true` or `false`

**When disabled:**

- Same edition can be downloaded multiple times
- No tracking records stored in MongoDB
- Useful for testing/debugging

**When enabled:**

- Prevents duplicate processing
- Stores edition history
- Honors retention period

#### Tracking Retention Days

How long to keep tracking records in MongoDB.

**Default:** 90 days
**Recommended range:** 30-180 days

**Considerations:**

- Longer retention = more storage, better history
- Shorter retention = less storage, recent editions only
- Old records automatically deleted during workflow

### SMTP Settings

#### SMTP Server

Mail server hostname for sending emails.

**Default:** From .env (`smtp.gmx.net`)
**Examples:**

- GMX: `smtp.gmx.net`
- Gmail: `smtp.gmail.com`
- Outlook: `smtp-mail.outlook.com`

**When to change:**

- Switching email providers
- Using different servers per environment

#### SMTP Port

Mail server port number.

**Default:** 587 (STARTTLS)
**Common ports:**

- `587`: STARTTLS (recommended)
- `465`: SSL/TLS
- `25`: Unencrypted (not recommended)

**Note:** Username and password remain in `.env` for security

---

## 🔄 Configuration Workflow

### Local Development

1. Set `.env` with your credentials
2. Run `init_app_config.py` once
3. Adjust MongoDB settings as needed
4. Test locally: `uv run python -m depotbutler full`

### Azure Production

1. Deploy with Azure secrets configured
2. MongoDB config automatically shared with local
3. Change settings in MongoDB (no redeployment!)
4. Next scheduled run uses new settings

### Environment-Specific Config

You can have different settings per environment by:

1. Using different MongoDB databases (`depotbutler-dev`, `depotbutler-prod`)
2. Or using same database with environment checks in code

---
⚙️ Advanced Environment Variable Configuration

The following settings can be configured via environment variables for advanced tuning:

### MongoDB Client Settings

Fine-tune MongoDB connection behavior (usually not needed):

```bash
# MongoDB client timeout settings (milliseconds)
MONGODB_SERVER_SELECTION_TIMEOUT_MS=5000  # Default: 5000ms
MONGODB_CONNECT_TIMEOUT_MS=10000          # Default: 10000ms
MONGODB_SOCKET_TIMEOUT_MS=30000           # Default: 30000ms
MONGODB_CURSOR_BATCH_SIZE=1000            # Default: 1000
```

**When to adjust:**

- Slow network connections: Increase timeouts
- MongoDB Atlas serverless: Increase `SERVER_SELECTION_TIMEOUT_MS`
- Large result sets: Adjust `CURSOR_BATCH_SIZE`

### HTTP Client Settings

Control HTTP request behavior for boersenmedien.com:

```bash
# HTTP client settings
HTTP_REQUEST_TIMEOUT=30.0    # Seconds, default: 30.0
HTTP_MAX_RETRIES=3            # Default: 3
HTTP_RETRY_BACKOFF=2.0        # Multiplier, default: 2.0
```

**When to adjust:**

- Slow downloads: Increase `REQUEST_TIMEOUT`
- Flaky network: Increase `MAX_RETRIES`
- Faster retries: Decrease `RETRY_BACKOFF`

### Notification Settings

Control notification behavior:

```bash
# Notification settings
NOTIFICATION_COOKIE_WARNING_DAYS=3             # Default: 3 days
NOTIFICATION_SEND_SUMMARY_EMAILS=true          # Default: true
NOTIFICATION_ADMIN_NOTIFICATION_ENABLED=true   # Default: true
```

**When to adjust:**

- More warning time: Increase `COOKIE_WARNING_DAYS`
- Reduce email noise: Set `SEND_SUMMARY_EMAILS=false`
- Disable all admin emails: Set `ADMIN_NOTIFICATION_ENABLED=false`

### Azure Blob Storage Settings

Configure PDF archival to Azure Blob Storage (added December 2025):

```bash
# Azure Blob Storage for long-term archival
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
AZURE_STORAGE_CONTAINER_NAME=editions    # Default: editions
AZURE_STORAGE_ENABLED=true               # Default: true
```

**Benefits of blob storage:**

- Historical edition archive (prevents re-downloads)
- Metadata storage (title, publication date, etc.)
- Cost-effective storage (Cool tier)
- Access to editions via Azure portal

**When to use:**

- Enable: For production deployments (long-term storage)
- Disable: For local development (leave `CONNECTION_STRING` empty)

**See also:** [VALIDATION_SETUP.md](VALIDATION_SETUP.md) for Azure Blob Storage setup

### Publication Discovery Settings

Control automatic publication synchronization:

```bash
# Publication discovery
DISCOVERY_ENABLED=true    # Default: true
```

**When to disable:**

- Testing specific publications
- Preventing unwanted publication additions
- Debugging sync issues

---

## 🔍 Troubleshooting

### Config not loading

**Symptom:** Changes in MongoDB not taking effect

**Solutions:**

1. Verify MongoDB connection: `$env:PYTHONPATH="src" ; uv run python scripts/init_app_config.py --verify`
2. Check document exists: `db.config.findOne({ _id: "app_config" })`
3. Verify connection string in `.env` is correct
4. Check logs for MongoDB connection errors

### Fallback to .env values

**Symptom:** System uses .env values instead of MongoDB

**Explanation:** This is by design! The system falls back to .env if:

- MongoDB connection fails
- `app_config` document doesn't exist
- Individual setting missing from MongoDB

**Solution:** Run `init_app_config.py` to create/update MongoDB config

### Admin emails not working

**Symptom:** Not receiving admin emails after adding to MongoDB

**Check:**

1. Verify email added correctly: `db.config.findOne({ _id: "app_config" }, { admin_emails: 1 })`
2. Check SMTP settings in `.env` are correct
3. Look for errors in logs during email sending
4. Test with existing `SMTP_ADMIN_ADDRESS` first

---

## 📚 Related Documentation

- [MONGODB.md](MONGODB.md) - MongoDB setup and data management
- [DEPLOYMENT.md](DEPLOYMENT.md) - Azure deployment with secrets
- [COOKIE_AUTHENTICATION.md](COOKIE_AUTHENTICATION.md) - Cookie management

---

## 💡 Best Practices

1. **Keep secrets in .env**: Never put passwords in MongoDB
2. **Use MongoDB for changeables**: Settings you adjust frequently
3. **Test locally first**: Verify config changes before Azure deployment
4. **Document changes**: Note why you changed settings (especially log level)
5. **Monitor logs**: Check that new settings are being applied
6. **Use version control for .env.example**: Track what settings exist

---

## 🆘 Quick Reference

### Check current config

```bash
$env:PYTHONPATH="src"
uv run python -c "import asyncio; from depotbutler.db.mongodb import get_mongodb_service; async def check(): m = await get_mongodb_service(); c = await m.db.config.find_one({'_id': 'app_config'}); print(c); asyncio.run(check())"
```

### Reset to defaults

```bash
$env:PYTHONPATH="src"
uv run python scripts/init_app_config.py
# Answer "yes" when asked to overwrite
```

### Add setting via CLI

```javascript
db.config.updateOne(
  { _id: "app_config" },
  { $set: { your_new_setting: "value" } }
)
```
