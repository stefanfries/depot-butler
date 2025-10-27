# Azure Container Apps Deployment Guide

## Setup for Daily Edition Tracking

### 1. Azure File Share Setup

To persist edition tracking across container restarts, set up an Azure File Share:

```bash
# Create storage account
az storage account create \
  --name depotbutlerstorage \
  --resource-group your-resource-group \
  --location westeurope \
  --sku Standard_LRS

# Create file share
az storage share create \
  --name depotbutler-data \
  --account-name depotbutlerstorage
```

### 2. Container App Configuration

Mount the file share in your Container App:

```yaml
apiVersion: 2023-05-01
kind: ContainerApp
properties:
  configuration:
    secrets:
      - name: "storage-key"
        value: "YOUR_STORAGE_ACCOUNT_KEY"
  template:
    volumes:
      - name: data-volume
        storageType: AzureFile
        storageName: depotbutler-storage
    containers:
      - name: depot-butler
        image: your-registry/depot-butler:latest
        volumeMounts:
          - mountPath: /mnt/data
            volumeName: data-volume
        env:
          - name: TRACKING_FILE_PATH
            value: "/mnt/data/processed_editions.json"
          - name: TRACKING_ENABLED
            value: "true"
```

### 3. Scheduled Execution

Set up the container to run daily at 4 PM (Monday-Friday):

```yaml
template:
  scale:
    minReplicas: 0
    maxReplicas: 1
    rules:
      - name: cron-scale-rule
        type: cron
        metadata:
          timezone: "Europe/Berlin"
          start: "0 16 * * 1-5"  # 4 PM Monday-Friday
          desiredReplicas: "1"
```

### 4. Environment Variables

Add to your .env file:

```
# Edition Tracking Settings
TRACKING_ENABLED=true
TRACKING_FILE_PATH=/mnt/data/processed_editions.json
TRACKING_RETENTION_DAYS=90
```

### 5. Manual Commands

**Check for new editions:**
```bash
az containerapp job start --name depot-butler-check --resource-group your-rg
```

**Force reprocess latest edition:**
```bash
az containerapp job start --name depot-butler-force --resource-group your-rg
```

## How It Works

1. **Daily Check**: Container starts every weekday at 4 PM
2. **Edition Detection**: Gets latest edition info from website
3. **Duplicate Prevention**: Checks tracking file for already processed editions
4. **Processing**: Only processes new editions (download + email + OneDrive)
5. **Tracking**: Marks edition as processed in persistent file
6. **Auto-Shutdown**: Container terminates after job completion (usually 1-2 minutes)
7. **Cleanup**: Automatically removes old tracking records after 90 days

## Benefits

- ✅ **No Duplicates**: Same edition never sent twice
- ✅ **Handles Schedule Variations**: Works if editions come Tuesday-Friday
- ✅ **Persistent**: Tracking survives container restarts
- ✅ **Self-Cleaning**: Old records automatically removed
- ✅ **Manual Override**: Can force reprocess if needed
- ✅ **Status Monitoring**: Can check processing status
- ✅ **Cost Efficient**: Runs only 1-2 minutes, then shuts down automatically