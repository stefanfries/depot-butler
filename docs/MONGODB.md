# 🗄️ MongoDB Data Management

This guide explains how to manage data stored in MongoDB Atlas.

---

## 📋 Overview

MongoDB stores five main types of data:

### 1. Publications (NEW)

Publication configurations with subscription metadata:

- ✅ **Database-Driven**: Publications managed in MongoDB instead of code
- ✅ **Automatic Metadata**: Extracts subscription details from account (Abo-Art, Laufzeit)
- ✅ **Delivery Preferences**: Control email/OneDrive per publication
- ✅ **Date Tracking**: Subscription start/end dates for lifecycle management
- ✅ **Easy Updates**: Change settings without redeployment

### 2. Recipients

Email recipients with statistics tracking:

- ✅ **Easy Updates**: Add/remove recipients without redeploying
- ✅ **Statistics Tracking**: Tracks send_count and last_sent_at for each recipient
- ✅ **Flexible**: Support for different recipient types (regular, admin)
- ✅ **Scalable**: No size limits like environment variables

### 3. Edition Tracking

Prevents duplicate email sending:

- ✅ **Centralized**: Single source of truth across local and Azure
- ✅ **No Duplicates**: Same edition never processed twice
- ✅ **Persistent**: Works across container restarts and environments
- ✅ **Auto-Cleanup**: Old records automatically removed after 90 days

### 4. Configuration (Auth Cookie)

Stores authentication cookie for boersenmedien.com:

- ✅ **Easy Updates**: Update cookie without redeployment
- ✅ **Centralized**: Same cookie used everywhere (local + Azure)
- ✅ **Expiration Tracking**: Automatic warnings when cookie expires soon
- ✅ **Simple Updates**: Helper script for cookie refresh

### 5. App Configuration

Dynamic application settings without redeployment:

- ✅ **LOG_LEVEL**: Change logging verbosity (INFO, DEBUG, WARNING, ERROR)
- ✅ **cookie_warning_days**: Adjust warning threshold (default: 5 days)
- ✅ **admin_emails**: Add/remove admin email addresses
- ✅ **No Redeployment**: Changes take effect on next workflow run
- ✅ **Environment Override**: Can still use environment variables if needed

---

## 🔧 Setup

### MongoDB Atlas Free Tier

1. **Create Account**: Go to [mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas)
2. **Create Cluster**: Select M0 (free tier, shared, 512MB storage)
3. **Configure Security**:
   - Create database user with password
   - Add IP whitelist: `0.0.0.0/0` (allow from anywhere) or your specific IPs

### Database Structure

```text
Database: depotbutler
Collections:
  - publications        # Publication configurations with metadata
  - recipients          # Email recipients with statistics
  - processed_editions  # Edition tracking to prevent duplicates
  - config              # Configuration storage
    - auth_cookie       # Authentication cookie document
    - app_config        # Application settings document
```

**Initial Setup:**

```bash
# Initialize app configuration in MongoDB
$env:PYTHONPATH="src" ; uv run python scripts/init_app_config.py

# Seed publications with subscription metadata
$env:PYTHONPATH="src" ; uv run python scripts/seed_publications.py
```

This creates the `app_config` document with defaults from your `.env` file and populates the `publications` collection with subscription metadata automatically extracted from your boersenmedien.com account.

### Publications Schema

```javascript
{
  publication_id: String,           // Unique ID (e.g., "megatrend-folger")
  name: String,                     // Display name (e.g., "Megatrend Folger")
  subscription_id: String,          // Subscription ID from account
  subscription_number: String,      // Subscription number (e.g., "AM-01029205")
  subscription_type: String,        // Type (e.g., "Jahresabo")
  duration: String,                 // Duration string (e.g., "02.07.2025 - 01.07.2026")
  duration_start: Date,             // Parsed start date
  duration_end: Date,               // Parsed end date
  email_enabled: Boolean,           // Enable email delivery
  onedrive_enabled: Boolean,        // Enable OneDrive upload
  default_onedrive_folder: String,  // Default folder path
  active: Boolean,                  // Publication active status
  created_at: Date,                 // When created
  updated_at: Date                  // Last update
}
```

### Recipient Schema

```javascript
{
  first_name: String,       // Used in email personalization
  last_name: String,        // For records
  email: String,            // Recipient email address (unique)
  active: Boolean,          // true = receives emails, false = paused
  recipient_type: String,   // "regular" or "admin"
  created_at: Date,         // When recipient was added
  last_sent_at: Date|null,  // Last email sent (null if never sent)
  send_count: Number        // Total emails sent to this recipient
}
```

### Edition Tracking Schema

```javascript
{
  edition_key: String,       // Unique key: "{publication_date}_{title}"
  title: String,             // Edition title (e.g., "Megatrend Folger 48/2025")
  publication_date: String,  // Publication date (YYYY-MM-DD)
  download_url: String,      // URL where PDF was downloaded from
  file_path: String,         // Local file path (if stored)
  processed_at: Date         // When edition was processed
}
```

### Config Schema (Auth Cookie)

```javascript
{
  _id: "auth_cookie",        // Document ID (always "auth_cookie")
  cookie_value: String,      // The .AspNetCore.Cookies value
  updated_at: Date,          // When cookie was last updated
  updated_by: String         // Who updated it (username/identifier)
}
```

---

## 📊 Managing Recipients

### Using MongoDB Compass (GUI)

1. **Download**: [MongoDB Compass](https://www.mongodb.com/products/compass)
2. **Connect**: Use connection string from Atlas
3. **Navigate**: `depotbutler` → `recipients`
4. **Add/Edit/Delete**: Use GUI buttons

### Using MongoDB Atlas Web UI

1. Go to Atlas → Browse Collections
2. Select `depotbutler` → `recipients`
3. Use "Insert Document" button to add recipients

### Using Python Script

Use the included utility script:

```powershell
# View all recipients with statistics
$env:PYTHONPATH="src"
uv run python scripts/check_recipients.py
```

---

## 🆕 Adding Recipients

### Via MongoDB Compass

1. Click "Add Data" → "Insert Document"
2. Use this template:

```javascript
{
  "first_name": "John",
  "last_name": "Doe",
  "email": "john.doe@example.com",
  "active": true,
  "recipient_type": "regular",
  "created_at": new Date(),
  "last_sent_at": null,
  "send_count": 0
}
```

### Via Atlas Web UI

Same as above, but use the web interface.

### Via mongosh (CLI)

```javascript
use depotbutler

db.recipients.insertOne({
  first_name: "John",
  last_name: "Doe",
  email: "john.doe@example.com",
  active: true,
  recipient_type: "regular",
  created_at: new Date(),
  last_sent_at: null,
  send_count: 0
})
```

---

## ✏️ Updating Recipients

### Pause a Recipient (Stop Emails)

```javascript
db.recipients.updateOne(
  { email: "john.doe@example.com" },
  { $set: { active: false } }
)
```

### Reactivate a Recipient

```javascript
db.recipients.updateOne(
  { email: "john.doe@example.com" },
  { $set: { active: true } }
)
```

### Change Recipient Type

```javascript
db.recipients.updateOne(
  { email: "john.doe@example.com" },
  { $set: { recipient_type: "admin" } }
)
```

### Update Email Address

```javascript
db.recipients.updateOne(
  { email: "old.email@example.com" },
  { $set: { email: "new.email@example.com" } }
)
```

---

## 🗑️ Removing Recipients

### Soft Delete (Recommended)

Deactivate instead of deleting to keep statistics:

```javascript
db.recipients.updateOne(
  { email: "john.doe@example.com" },
  { $set: { active: false } }
)
```

### Hard Delete

Permanently remove (lose statistics):

```javascript
db.recipients.deleteOne({ email: "john.doe@example.com" })
```

---

## 📈 Viewing Statistics

### All Recipients with Stats

```javascript
db.recipients.find(
  {},
  { 
    first_name: 1, 
    last_name: 1, 
    email: 1, 
    active: 1,
    send_count: 1, 
    last_sent_at: 1,
    _id: 0 
  }
).sort({ email: 1 })
```

### Only Active Recipients

```javascript
db.recipients.find(
  { active: true },
  { first_name: 1, email: 1, send_count: 1, _id: 0 }
)
```

### Recipients Who Haven't Received Email Yet

```javascript
db.recipients.find(
  { last_sent_at: null },
  { first_name: 1, email: 1, created_at: 1, _id: 0 }
)
```

### Top Recipients by Send Count

```javascript
db.recipients.find(
  {},
  { first_name: 1, email: 1, send_count: 1, _id: 0 }
).sort({ send_count: -1 }).limit(10)
```

---

## 📰 Viewing Edition Tracking

### Recently Processed Editions (Last 30 Days)

```javascript
db.processed_editions.find(
  { processed_at: { $gte: new Date(Date.now() - 30*24*60*60*1000) } },
  { title: 1, publication_date: 1, processed_at: 1, _id: 0 }
).sort({ processed_at: -1 })
```

### All Processed Editions

```javascript
db.processed_editions.find(
  {},
  { title: 1, publication_date: 1, processed_at: 1, _id: 0 }
).sort({ processed_at: -1 })
```

### Check If Specific Edition Was Processed

```javascript
db.processed_editions.findOne(
  { edition_key: "2025-11-26_Megatrend Folger 48/2025" },
  { title: 1, processed_at: 1, _id: 0 }
)
```

### Count Total Processed Editions

```javascript
db.processed_editions.countDocuments()
```

### Remove Old Edition Tracking (Manual Cleanup)

```javascript
// Remove editions older than 90 days
db.processed_editions.deleteMany({
  processed_at: { $lt: new Date(Date.now() - 90*24*60*60*1000) }
})
```

**Note:** Edition cleanup happens automatically via the application, so manual cleanup is usually not needed.

---

## 🔒 Security Best Practices

### 1. Strong Password

Use a strong password for MongoDB user:

- At least 16 characters
- Mix of uppercase, lowercase, numbers, symbols
- Avoid common words

### 2. IP Whitelist

For production, restrict to Azure Container Apps IP range instead of `0.0.0.0/0`.

### 3. Connection String Security

- **Never commit** connection strings to git
- Store in `.env` file (already in `.gitignore`)
- URL-encode special characters:
  - `#` → `%23`
  - `@` → `%40`
  - `%` → `%25`

### 4. Backup

MongoDB Atlas Free Tier doesn't include automated backups:

- Manually export collection periodically
- Or upgrade to M10+ for automated backups

---

## 🔧 Troubleshooting

### Connection Timeout

1. Check IP whitelist includes your IP or `0.0.0.0/0`
2. Verify connection string is correct
3. Check password is URL-encoded

### Authentication Failed

1. Verify username and password are correct
2. Check password is URL-encoded (especially `#` → `%23`)
3. Ensure user has read/write permissions on database

### No Recipients Found

```javascript
// Check if collection exists and has documents
db.recipients.countDocuments()

// If 0, add recipients using examples above
```

### Can't View Edition Tracking

```javascript
// Check if processed_editions collection exists
db.processed_editions.countDocuments()

// If 0, no editions have been processed yet - run the workflow first
```

---

## 🔑 Managing Authentication Cookie

### View Current Cookie

```javascript
db.config.findOne({ _id: "auth_cookie" })
```

### Update Cookie (MongoDB Compass)

1. Navigate to `config` collection
2. Find document with `_id: "auth_cookie"`
3. Edit the `cookie_value` field
4. Update `updated_at` to current date
5. Update `updated_by` to your name
6. Save changes

### Update Cookie (Using Script) - **RECOMMENDED**

```bash
uv run python scripts/update_cookie_mongodb.py
```

Follow the prompts:

1. Login to boersenmedien.com in your browser
2. Copy the `.AspNetCore.Cookies` value from DevTools
3. Paste into the script
4. Done! Cookie is now available everywhere

### Verify Cookie

```bash
uv run python scripts/update_cookie_mongodb.py --verify
```

### Check When Cookie Was Last Updated

```javascript
db.config.findOne(
  { _id: "auth_cookie" },
  { cookie_value: 0, _id: 0 }  // Hide cookie value for security
)
```

---

## ⚙️ App Configuration Management

### Overview

The `app_config` document stores dynamic settings that can be changed without redeployment:

```javascript
{
  "_id": "app_config",
  "log_level": "INFO",          // DEBUG, INFO, WARNING, ERROR
  "cookie_warning_days": 5,     // Days before expiration to send warning
  "admin_emails": [             // List of admin email addresses
    "admin@example.com",
    "backup@example.com"
  ]
}
```

### Change Settings

Use MongoDB Compass or mongosh to edit the `app_config` document:

```javascript
// Change log level to DEBUG
db.config.updateOne(
  { _id: "app_config" },
  { $set: { log_level: "DEBUG" } }
)

// Adjust cookie warning threshold
db.config.updateOne(
  { _id: "app_config" },
  { $set: { cookie_warning_days: 7 } }
)

// Add an admin email
db.config.updateOne(
  { _id: "app_config" },
  { $push: { admin_emails: "newadmin@example.com" } }
)

// Remove an admin email
db.config.updateOne(
  { _id: "app_config" },
  { $pull: { admin_emails: "oldadmin@example.com" } }
)
```

**Changes take effect on the next workflow run - no redeployment needed!**

See [CONFIGURATION.md](CONFIGURATION.md) for detailed configuration guide.

---

## � Managing Publications

### Publication Overview

Publications are automatically populated from your boersenmedien.com account subscriptions. The system extracts:

- Subscription metadata (ID, number, type)
- Duration information with parsed dates
- Delivery preferences (email, OneDrive)

### Seeding Publications

Run this script to discover subscriptions and populate MongoDB:

```bash
$env:PYTHONPATH="src"
uv run python scripts/seed_publications.py
```

**What it does:**

1. ✅ Discovers all active subscriptions from your account
2. ✅ Extracts metadata: Abo-Art (subscription type), Laufzeit (duration)
3. ✅ Parses German date format to structured dates
4. ✅ Maps subscriptions to configured publications
5. ✅ Creates/updates publication documents in MongoDB

**Output example:**

```text
Found subscription: Megatrend Folger (ID: 2477462, Type: Jahresabo, Duration: 02.07.2025 - 01.07.2026)
✓ Created Megatrend Folger
```

### Viewing Publications

```javascript
// Find all active publications
db.publications.find({ active: true })

// Find specific publication
db.publications.findOne({ publication_id: "megatrend-folger" })

// Check subscription expiration dates
db.publications.find(
  { duration_end: { $lt: new Date("2026-01-01") } },
  { name: 1, duration: 1, duration_end: 1 }
)
```

### Updating Publications

```javascript
// Disable email for a publication
db.publications.updateOne(
  { publication_id: "der-aktionaer-epaper" },
  { $set: { email_enabled: false, updated_at: new Date() } }
)

// Change OneDrive folder
db.publications.updateOne(
  { publication_id: "megatrend-folger" },
  { $set: { default_onedrive_folder: "NewFolder", updated_at: new Date() } }
)

// Deactivate a publication
db.publications.updateOne(
  { publication_id: "megatrend-folger" },
  { $set: { active: false, updated_at: new Date() } }
)
```

**Re-run the seed script** to refresh metadata from your account:

```bash
$env:PYTHONPATH="src"; uv run python scripts/seed_publications.py
```

This will update existing publications with latest subscription information.

---

## 📚 Additional Resources

- [MongoDB Atlas Documentation](https://docs.atlas.mongodb.com/)
- [MongoDB Query Language](https://docs.mongodb.com/manual/tutorial/query-documents/)
- [Motor Documentation](https://motor.readthedocs.io/) (Async driver used in code)

---

**Last Updated:** December 13, 2025
