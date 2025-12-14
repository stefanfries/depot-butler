# 📁 OneDrive Folder Configuration

This guide explains how OneDrive folder paths are configured in Depot Butler.

---

## 🏗️ Architecture

Folder paths use a **two-level configuration**:

1. **Per-Publication Default** (required) - Stored in `publications` collection
2. **Per-Recipient Override** (optional) - Stored in `publication_preferences` array

### Resolution Priority

```text
1. Check: recipient.publication_preferences[].custom_onedrive_folder
   └─ If set → Use this path
   
2. Fallback: publication.default_onedrive_folder
   └─ Always defined for each publication
```

---

## 📊 Current Configuration

### Publication Defaults

View with: `python scripts/seed_publications.py` or query MongoDB:

```javascript
db.publications.find({}, {
  publication_id: 1,
  name: 1,
  default_onedrive_folder: 1
})
```

**Current defaults**:

```javascript
{
  "publication_id": "megatrend-folger",
  "name": "Megatrend Folger",
  "default_onedrive_folder": "Dokumente/Banken/DerAktionaer/Strategie_800-Prozent"
}

{
  "publication_id": "der-aktionaer-epaper",
  "name": "DER AKTIONÄR Magazin",
  "default_onedrive_folder": "Dokumente/Banken/DerAktionaer/Magazin"
}
```

### Recipient Overrides

View with: `python scripts/check_recipients.py`

**Current state**: All 5 recipients use publication defaults (no custom folders configured).

---

## 🔧 Configuration Examples

### Change Publication Default Folder

Updates **all recipients** who don't have a custom override:

```javascript
db.publications.updateOne(
  { publication_id: "megatrend-folger" },
  { $set: { default_onedrive_folder: "Dokumente/NewPath" } }
)
```

### Set Custom Folder for Specific Recipient

Only affects **one recipient** for **one publication**:

```javascript
db.recipients.updateOne(
  {
    email: "stefan.fries.burgdorf@gmx.de",
    "publication_preferences.publication_id": "megatrend-folger"
  },
  {
    $set: {
      "publication_preferences.$.custom_onedrive_folder": "Dokumente/Stefan/Special"
    }
  }
)
```

### Remove Custom Override (Use Default Again)

```javascript
db.recipients.updateOne(
  {
    email: "stefan.fries.burgdorf@gmx.de",
    "publication_preferences.publication_id": "megatrend-folger"
  },
  {
    $unset: {
      "publication_preferences.$.custom_onedrive_folder": ""
    }
  }
)
```

### View All Custom Folders

```javascript
db.recipients.aggregate([
  { $unwind: "$publication_preferences" },
  { $match: { "publication_preferences.custom_onedrive_folder": { $exists: true } } },
  {
    $project: {
      _id: 0,
      email: 1,
      publication: "$publication_preferences.publication_id",
      custom_folder: "$publication_preferences.custom_onedrive_folder"
    }
  }
])
```

---

## 📝 Schema

### Publication Schema

```javascript
{
  "_id": ObjectId("..."),
  "publication_id": "megatrend-folger",
  "name": "Megatrend Folger",
  "default_onedrive_folder": "Dokumente/Banken/DerAktionaer/Strategie_800-Prozent",
  // ... other fields
}
```

### Recipient Schema

```javascript
{
  "_id": ObjectId("..."),
  "email": "stefan.fries.burgdorf@gmx.de",
  "first_name": "Stefan",
  "last_name": "Fries",
  "active": true,
  "publication_preferences": [
    {
      "publication_id": "megatrend-folger",
      "enabled": true,
      "email_enabled": true,
      "upload_enabled": true,
      "custom_onedrive_folder": "Dokumente/Stefan/Special",  // ← OPTIONAL override
      "organize_by_year": null,
      "overwrite_files": null
    }
  ]
}
```

---

## ⚙️ Additional Settings

Besides `custom_onedrive_folder`, recipients can also override:

- `organize_by_year`: `true` to create year subfolders (e.g., `2024/`), `false` to skip
- `overwrite_files`: `true` to replace existing files, `false` to skip duplicates

**Example**: Set custom folder AND disable year organization:

```javascript
db.recipients.updateOne(
  {
    email: "stefan.fries.burgdorf@gmx.de",
    "publication_preferences.publication_id": "megatrend-folger"
  },
  {
    $set: {
      "publication_preferences.$.custom_onedrive_folder": "Dokumente/Flat",
      "publication_preferences.$.organize_by_year": false
    }
  }
)
```

This would store files directly in `Dokumente/Flat/` without year subfolders.

---

## 🚀 Testing

After configuration changes:

1. **Verify configuration**:

   ```bash
   python scripts/check_recipients.py
   ```

2. **Test locally**:

   ```bash
   $env:PYTHONPATH="src" ; uv run python -m depotbutler.main
   ```

3. **Check OneDrive**:
   - Files should appear in configured folders
   - Year subfolders created if `organize_by_year=true`

---

## 🔍 Troubleshooting

### Files Going to Wrong Folder

1. Check recipient's custom override:

   ```javascript
   db.recipients.findOne(
     { email: "user@example.com" },
     { "publication_preferences": 1 }
   )
   ```

2. Check publication default:

   ```javascript
   db.publications.findOne(
     { publication_id: "megatrend-folger" },
     { default_onedrive_folder: 1 }
   )
   ```

3. Run with debug logging:

   ```bash
   $env:LOG_LEVEL="DEBUG"
   $env:PYTHONPATH="src"
   uv run python -m depotbutler.main
   ```

   Look for: `"Using publication folder: ..."` in logs.

---

## 📚 Related Documentation

- [MONGODB.md](MONGODB.md) - Complete MongoDB schema and management
- [decisions.md](decisions.md) - ADR-003 explains per-recipient preferences design
- [SPRINT3_PLAN.md](SPRINT3_PLAN.md) - Multi-publication implementation details
- [ONEDRIVE_SETUP.md](ONEDRIVE_SETUP.md) - OneDrive OAuth setup and deployment
