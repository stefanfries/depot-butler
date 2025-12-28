# 🚀 Azure Deployment Guide

This guide explains how to deploy depot-butler to Azure Container Apps.

---

## 🎯 How It Works

Once deployed, the system operates automatically:

1. **Scheduled Check**: Container starts every weekday at 4 PM German time
2. **Edition Detection**: Gets latest edition info from Börsenmedien website
3. **Duplicate Prevention**: Checks MongoDB for already processed editions
4. **Processing**: Only processes new editions (download + email + OneDrive)
5. **Tracking**: Marks edition as processed in MongoDB
6. **Auto-Shutdown**: Container terminates after job completion (typically 1-2 minutes)
7. **Cleanup**: Automatically removes old tracking records after 90 days

### Benefits

- ✅ **No Duplicates**: Same edition never sent twice (centralized MongoDB tracking)
- ✅ **Handles Schedule Variations**: Works if editions come Tuesday-Friday
- ✅ **Persistent**: Tracking survives container restarts and works across environments
- ✅ **Self-Cleaning**: Old records automatically removed
- ✅ **Manual Override**: Can force reprocess if needed
- ✅ **Cost Efficient**: Runs only 1-2 minutes per execution

---

## 📋 Prerequisites

1. ✅ Azure subscription with Container Apps enabled
2. ✅ Azure CLI installed and authenticated (`az login`)
3. ✅ Docker image built and pushed to GitHub Container Registry
4. ✅ MongoDB Atlas cluster set up (free tier works)
5. ✅ All secrets and credentials ready

---

## 🔧 Deployment Steps

### Step 1: Configure Environment Variables

The deployment script reads all secrets from your `.env` file.

1. **Copy the template file:**

   ```powershell
   cp .env.example .env
   ```

2. **Edit `.env` and fill in all required values:**

   ```bash
   # Börsenmedien Credentials
   BOERSENMEDIEN_USERNAME=your.email@example.com
   BOERSENMEDIEN_PASSWORD=your_actual_password

   # OneDrive OAuth (run setup_onedrive_auth.py to generate ONEDRIVE_REFRESH_TOKEN)
   ONEDRIVE_CLIENT_ID=your_client_id
   ONEDRIVE_CLIENT_SECRET=your_client_secret
   ONEDRIVE_REFRESH_TOKEN=your_refresh_token

   # SMTP Configuration
   SMTP_USERNAME=your.email@gmail.com
   SMTP_PASSWORD=your_app_password
   SMTP_ADMIN_ADDRESS=admin@example.com

   # MongoDB Atlas Configuration
   DB_NAME=depotbutler
   DB_ROOT_USERNAME=admin
   DB_ROOT_PASSWORD=your_mongodb_password
   # Format: mongodb+srv://[username]:[password]@[cluster-url]/[options]
   DB_CONNECTION_STRING=mongodb+srv://...

   # Azure Blob Storage (Archival - Sprint 5)
   AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=..."

   # Discovery Settings
   DISCOVERY_ENABLED=true
   ```

3. **⚠️ IMPORTANT:** The `.env` file is already in `.gitignore` and will NOT be committed to git!

### MongoDB Setup

Before deployment, set up MongoDB Atlas and create the recipients collection:

1. **Create MongoDB Atlas Cluster** (free tier M0 works perfectly)
   - Go to [mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas)
   - Create a free cluster
   - Create database user with read/write permissions
   - Add your IP or allow access from anywhere (0.0.0.0/0)

2. **Create Database and Collection:**

   ```javascript
   // In MongoDB Compass or Atlas web interface
   use depotbutler
   db.createCollection("recipients")
   ```

3. **Add Recipients:**

   ```javascript
   db.recipients.insertMany([
     {
       first_name: "John",
       last_name: "Doe",
       email: "john.doe@example.com",
       active: true,
       recipient_type: "regular",
       created_at: new Date(),
       last_sent_at: null,
       send_count: 0
     }
   ])
   ```

4. **URL-Encode Password:** If your MongoDB password contains special characters like `#`, encode them:
   - `#` → `%23`
   - `@` → `%40`
   - Example: `password#123` becomes `password%23123`

### Step 2: Run Deployment

```powershell
# Make sure you're logged into Azure
az login

# Run the deployment script from project root
.\deploy-to-azure.ps1
```

The script will automatically:

1. ✅ Read all secrets from your `.env` file
2. ✅ Get storage account key
3. ✅ Create Container App Job with environment variables
4. ✅ Configure all secrets (including MongoDB credentials and Azure Storage)
5. ✅ Create Azure File Share for temp storage
6. ✅ Set up cron schedule (Monday-Friday at 3 PM UTC / 4 PM German time)

**Note:** Volume mount configuration is done separately via YAML (see Step 2a below).

### Step 2a: Configure Volume Mount (Manual - One-Time Setup)

The volume mount at `/mnt/data` is **required** for the workflow. PDFs are downloaded to this temp directory before being emailed, uploaded to OneDrive, and archived to blob storage.

**Why Manual Configuration?** Azure CLI's `--set` syntax doesn't work reliably with array properties like volumes. The YAML approach is more reliable.

**Steps:**

1. **Export current job configuration:**
   ```powershell
   az containerapp job show --name depot-butler-job --resource-group rg-FastAPI-AzureContainerApp-dev --output yaml > job-config.yaml
   ```

2. **Edit `job-config.yaml`** to add volume configuration:

   Find the section:
   ```yaml
   template:
     containers:
     - image: ghcr.io/stefanfries/depot-butler:latest
       name: depot-butler-job
       resources:
         cpu: 1.0
         memory: 2Gi
     volumes: null
   ```

   Replace with:
   ```yaml
   template:
     containers:
     - image: ghcr.io/stefanfries/depot-butler:latest
       name: depot-butler-job
       resources:
         cpu: 1.0
         memory: 2Gi
       volumeMounts:
       - volumeName: data-volume
         mountPath: /mnt/data
     volumes:
     - name: data-volume
       storageType: AzureFile
       storageName: depot-data-storage
   ```

3. **Apply the updated configuration:**
   ```powershell
   az containerapp job update --name depot-butler-job --resource-group rg-FastAPI-AzureContainerApp-dev --yaml job-config.yaml
   ```

4. **Verify the mount:**
   ```powershell
   az containerapp job show --name depot-butler-job --resource-group rg-FastAPI-AzureContainerApp-dev --query "properties.template.{volumes:volumes,volumeMounts:containers[0].volumeMounts}" --output json
   ```

   Expected output:
   ```json
   {
     "volumeMounts": [
       {
         "mountPath": "/mnt/data",
         "volumeName": "data-volume"
       }
     ],
     "volumes": [
       {
         "name": "data-volume",
         "storageName": "depot-data-storage",
         "storageType": "AzureFile"
       }
     ]
   }
   ```

5. **Cleanup:**
   ```powershell
   Remove-Item job-config.yaml
   ```

**Troubleshooting:** If volume mount fails, ensure the Azure File Share exists:
```powershell
az storage share show --name "depot-butler-data" --account-name depotbutlerstorage
# If not exists, create it:
az storage share create --name "depot-butler-data" --account-name depotbutlerstorage
```

### Azure Resources Created

- **Storage Account (Temp Files):** `depotbutlerstorage`
  - File Share: `depot-butler-data` (for temporary PDF downloads)
  - Mount Path: `/mnt/data` in container
- **Storage Account (Archival):** `depotbutlerarchive`
  - Container: `editions` (Cool tier, long-term retention)
  - Format: `{year}/{publication_id}/{filename}.pdf`
- **MongoDB:** Edition tracking, recipients, blob metadata stored in MongoDB Atlas (external)

**Note:** Recipients and edition tracking are managed in MongoDB Atlas, not in Azure. Use MongoDB Compass or the Atlas web interface to add/remove recipients or view processing history.

### Step 3: Verify Deployment

```powershell
# Check job status
az containerapp job show `
  --name depot-butler-job `
  --resource-group rg-FastAPI-AzureContainerApp-dev `
  --query "{Name:name, Status:properties.provisioningState, Cron:properties.configuration.scheduleTriggerConfig.cronExpression}"

# Test manual run
az containerapp job start `
  --name depot-butler-job `
  --resource-group rg-FastAPI-AzureContainerApp-dev

# View logs
az containerapp job logs show `
  --name depot-butler-job `
  --resource-group rg-FastAPI-AzureContainerApp-dev `
  --container depot-butler-job `
  --follow
```

---

## 🔄 Updating the Deployment

### Update Environment Variables Only

```powershell
# Update a single environment variable
az containerapp job update `
  --name depot-butler-job `
  --resource-group rg-FastAPI-AzureContainerApp-dev `
  --set-env-vars "TRACKING_RETENTION_DAYS=120"

# Update MongoDB connection string (if password changed)
az containerapp job secret set `
  --name depot-butler-job `
  --resource-group rg-FastAPI-AzureContainerApp-dev `
  --secrets "db-connection-string=<your-mongodb-connection-string>"
```

### Update Docker Image

```powershell
# Pull latest image and restart
az containerapp job update `
  --name depot-butler-job `
  --resource-group rg-FastAPI-AzureContainerApp-dev `
  --image "ghcr.io/stefanfries/depot-butler:latest"
```

### Update Cron Schedule

See `TIMEZONE_REMINDERS.md` for seasonal adjustments.

```powershell
# Winter time (CET): 3 PM UTC = 4 PM German time
az containerapp job update `
  --name depot-butler-job `
  --resource-group rg-FastAPI-AzureContainerApp-dev `
  --cron-expression "0 15 * * 1-5"

# Summer time (CEST): 2 PM UTC = 4 PM German time
az containerapp job update `
  --name depot-butler-job `
  --resource-group rg-FastAPI-AzureContainerApp-dev `
  --cron-expression "0 14 * * 1-5"
```

---

## 🔐 Security Best Practices

### 1. Never Commit Secrets

- ✅ The `.env` file is in `.gitignore` and will NOT be committed
- ✅ The template `deploy-to-azure.ps1` has no secrets (safe to commit)
- ✅ Use `.env.example` as a template for new setups

### 2. Rotate Secrets Regularly

```powershell
# Update OneDrive client secret (before it expires)
az containerapp job update `
  --name depot-butler-job `
  --resource-group rg-FastAPI-AzureContainerApp-dev `
  --secrets "onedrive-client-secret=NEW_SECRET_VALUE"
```

### 3. Use Managed Identity (Advanced)

For production, consider using Azure Managed Identity instead of storing secrets.

---

## 🐛 Troubleshooting

### Duplicate Email Notifications

**Issue:** Receiving duplicate notification emails (e.g., cookie warnings, error messages sent twice).

**Root Cause:** Azure Container Apps Job retry mechanism. When a job fails, Azure automatically retries based on `--replica-retry-limit` setting.

**Solution:** The deployment script is configured with `--replica-retry-limit 0` to prevent automatic retries, since most failures (authentication, configuration errors) are not transient and won't be resolved by immediate retry.

**For existing jobs:** The Azure CLI `update` command doesn't reliably change this setting. Update it manually in Azure Portal:

1. Navigate to the Container App Job
2. Configuration → Replica retry limit
3. Change from 1 to 0
4. Save

**When Retries Would Help:** Network timeouts, temporary service outages (TransientError exceptions). These are handled at the application level with exponential backoff.

### Deployment Fails

```powershell
# Check last error
az containerapp job execution list `
  --name depot-butler-job `
  --resource-group rg-FastAPI-AzureContainerApp-dev `
  --query "[0].{Status:properties.status, Error:properties.statusDetails}" `
  --output json
```

### Job Not Running on Schedule

1. Check cron expression is correct for current timezone
2. Verify job is not suspended: `az containerapp job show ...`
3. Check execution history in Azure Portal

### Environment Variables Not Working

```powershell
# List all environment variables
az containerapp job show `
  --name depot-butler-job `
  --resource-group rg-FastAPI-AzureContainerApp-dev `
  --query "properties.template.containers[0].env" `
  --output table
```

---

## 📊 Monitoring

### View Execution History

Azure Portal → Resource Groups → rg-FastAPI-AzureContainerApp-dev → depot-butler-job → Execution history

### Set Up Alerts

Configure Azure Monitor alerts for:

- Job failures
- Long execution times (> 30 minutes)
- Missing scheduled runs

---

## 📚 Related Documentation

- [Azure Container Apps Jobs](https://learn.microsoft.com/en-us/azure/container-apps/jobs)
- [ONEDRIVE_SETUP.md](./ONEDRIVE_SETUP.md) - OneDrive OAuth setup
- [TIMEZONE_REMINDERS.md](./TIMEZONE_REMINDERS.md) - Seasonal cron adjustments

---

---

## 🗄️ Blob Storage Archival (Sprint 5)

**Status:** ✅ Enabled in production since December 28, 2025

All processed editions are automatically archived to Azure Blob Storage for long-term retention.

### Configuration

**Storage Account:** `depotbutlerarchive` (Germany West Central, Cool tier)

- **Container:** `editions`
- **Path Format:** `{year}/{publication_id}/{filename}.pdf`
- **Example:** `2025/megatrend-folger/2025-12-18_Megatrend-Folger_51-2025.pdf`

### Features

1. **Non-blocking:** Archival failures don't impact email/OneDrive delivery
2. **Automatic:** All editions archived after successful processing
3. **Metadata:** MongoDB tracks blob URL, path, container, file size, archived timestamp
4. **Cache:** `--use-cache` flag enables retrieval from blob instead of website
5. **Cost-efficient:** Cool tier for archival access pattern (4x cheaper than Hot)

### Monitoring

Check archival status in MongoDB:

```javascript
db.processed_editions.find(
  { blob_url: { $exists: true } },
  { title: 1, issue: 1, blob_url: 1, archived_at: 1, file_size_bytes: 1 }
).sort({ archived_at: -1 })
```

View blob storage costs in Azure Portal:

```text
Cost Management → Cost Analysis → Filter by depotbutlerarchive
```

### Troubleshooting

If archival fails:

1. Check connection string is configured: `az containerapp job show ...`
2. Verify storage account accessible: `az storage account show --name depotbutlerarchive`
3. Check container exists: `az storage container show --name editions --account-name depotbutlerarchive`
4. Review logs for specific error: `az containerapp job logs show ...`

**Note:** Workflow continues even if archival fails. Check MongoDB `archived_at` field to confirm successful archival.

---

**Last Updated:** December 28, 2025
