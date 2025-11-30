# ⚙️ Configuration Guide

This guide explains how to configure depot-butler using both environment variables (.env) and MongoDB-based dynamic configuration.

---

## 📋 Configuration Architecture

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
  "admin_emails": ["admin@example.com"]  // from SMTP_ADMIN_ADDRESS
}
```

---

## 🎛️ MongoDB Dynamic Configuration

### Available Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `log_level` | String | `INFO` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `cookie_warning_days` | Number | `5` | Days before cookie expiration to send warning emails |
| `admin_emails` | Array | From .env | List of email addresses to receive admin notifications |

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

**Default:** 5 days  
**Recommended range:** 3-7 days

**Example scenarios:**
- Set to `7` if you check emails infrequently
- Set to `3` if you want minimal warning emails
- Set to `1` for last-minute reminders only

**How warnings work:**
- Warning emails sent daily once threshold is reached
- Error email sent immediately when cookie expires
- Warnings continue until you update the cookie

### Admin Emails

List of email addresses that receive:
- Success notifications (edition downloaded and uploaded)
- Error notifications (failures, cookie expiration warnings)
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
