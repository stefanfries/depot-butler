# 🗄️ MongoDB Recipients Management

This guide explains how to manage email recipients stored in MongoDB Atlas.

---

## 📋 Overview

Recipients are stored in MongoDB instead of environment variables for better management:

- ✅ **Easy Updates**: Add/remove recipients without redeploying
- ✅ **Statistics Tracking**: Tracks send_count and last_sent_at for each recipient
- ✅ **Flexible**: Support for different recipient types (regular, admin)
- ✅ **Scalable**: No size limits like environment variables

---

## 🔧 Setup

### MongoDB Atlas Free Tier

1. **Create Account**: Go to [mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas)
2. **Create Cluster**: Select M0 (free tier, shared, 512MB storage)
3. **Configure Security**:
   - Create database user with password
   - Add IP whitelist: `0.0.0.0/0` (allow from anywhere) or your specific IPs

### Database Structure

```
Database: depotbutler
Collection: recipients
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

---

## 📚 Additional Resources

- [MongoDB Atlas Documentation](https://docs.atlas.mongodb.com/)
- [MongoDB Query Language](https://docs.mongodb.com/manual/tutorial/query-documents/)
- [Motor Documentation](https://motor.readthedocs.io/) (Async driver used in code)

---

**Last Updated:** November 23, 2025
