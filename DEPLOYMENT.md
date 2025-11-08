# 🚀 Azure Deployment Guide

This guide explains how to deploy depot-butler to Azure Container Apps.

---

## 🎯 How It Works

Once deployed, the system operates automatically:

1. **Scheduled Check**: Container starts every weekday at 4 PM German time
2. **Edition Detection**: Gets latest edition info from Börsenmedien website
3. **Duplicate Prevention**: Checks tracking file for already processed editions
4. **Processing**: Only processes new editions (download + email + OneDrive)
5. **Tracking**: Marks edition as processed in persistent file
6. **Auto-Shutdown**: Container terminates after job completion (typically 1-2 minutes)
7. **Cleanup**: Automatically removes old tracking records after 90 days

### Benefits

- ✅ **No Duplicates**: Same edition never sent twice
- ✅ **Handles Schedule Variations**: Works if editions come Tuesday-Friday
- ✅ **Persistent**: Tracking survives container restarts
- ✅ **Self-Cleaning**: Old records automatically removed
- ✅ **Manual Override**: Can force reprocess if needed
- ✅ **Cost Efficient**: Runs only 1-2 minutes per execution

---

## 📋 Prerequisites

1. ✅ Azure subscription with Container Apps enabled
2. ✅ Azure CLI installed and authenticated (`az login`)
3. ✅ Docker image built and pushed to GitHub Container Registry
4. ✅ All secrets and credentials ready

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
   SMTP_RECIPIENTS=["recipient1@example.com","recipient2@example.com"]
   SMTP_ADMIN_ADDRESS=admin@example.com
   ```

3. **⚠️ IMPORTANT:** The `.env` file is already in `.gitignore` and will NOT be committed to git!

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
4. ✅ Configure all secrets
5. ✅ Mount Azure File Share (`depotbutlerstorage/depotbutler-data` at `/mnt/data`)
6. ✅ Set up cron schedule (Monday-Friday at 3 PM UTC / 4 PM German time)

### Azure Resources Created

- **Storage Account:** `depotbutlerstorage`
- **File Share:** `depotbutler-data` (for persistent edition tracking)
- **Mount Path:** `/mnt/data` in container
- **Tracking File:** `/mnt/data/processed_editions.json`

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

# Update a secret
az containerapp job update `
  --name depot-butler-job `
  --resource-group rg-FastAPI-AzureContainerApp-dev `
  --secrets "smtp-recipients=[\"new@email.com\",\"another@email.com\"]"
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

**Last Updated:** November 8, 2025
