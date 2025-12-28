# Azure Container App Job Deployment Script
# This script creates the depot-butler scheduled job in Azure
#
# ⚠️ IMPORTANT:
# 1. Make sure your .env file contains all required secrets
# 2. The .env file is in .gitignore and will NOT be committed to git
# 3. Run this script from the project root directory

# Configuration
$RESOURCE_GROUP = "rg-FastAPI-AzureContainerApp-dev"
$ENVIRONMENT = "managedEnvironment-rgFastAPIAzureC-a4a6"
$STORAGE_ACCOUNT = "depotbutlerstorage"
$JOB_NAME = "depot-butler-job"

Write-Host "🚀 Deploying depot-butler to Azure Container Apps..." -ForegroundColor Green

# Function to read .env file
function Get-EnvVariable {
    param (
        [string]$Name
    )

    $envFile = ".env"
    if (-not (Test-Path $envFile)) {
        Write-Host "❌ Error: .env file not found in current directory" -ForegroundColor Red
        exit 1
    }

    $content = Get-Content $envFile
    foreach ($line in $content) {
        if ($line -match "^\s*$Name\s*=\s*(.+)$") {
            $value = $matches[1]
            # Remove quotes if present
            $value = $value -replace '^[''"]|[''"]$', ''
            return $value
        }
    }

    Write-Host "⚠️  Warning: $Name not found in .env file" -ForegroundColor Yellow
    return $null
}

# Read secrets from .env file
Write-Host "📖 Reading configuration from .env file..." -ForegroundColor Cyan
$BOERSENMEDIEN_BASE_URL = Get-EnvVariable "BOERSENMEDIEN_BASE_URL"
$BOERSENMEDIEN_LOGIN_URL = Get-EnvVariable "BOERSENMEDIEN_LOGIN_URL"
$BOERSENMEDIEN_USERNAME = Get-EnvVariable "BOERSENMEDIEN_USERNAME"
$BOERSENMEDIEN_PASSWORD = Get-EnvVariable "BOERSENMEDIEN_PASSWORD"
$ONEDRIVE_CLIENT_ID = Get-EnvVariable "ONEDRIVE_CLIENT_ID"
$ONEDRIVE_CLIENT_SECRET = Get-EnvVariable "ONEDRIVE_CLIENT_SECRET"
$ONEDRIVE_REFRESH_TOKEN = Get-EnvVariable "ONEDRIVE_REFRESH_TOKEN"
$SMTP_USERNAME = Get-EnvVariable "SMTP_USERNAME"
$SMTP_PASSWORD = Get-EnvVariable "SMTP_PASSWORD"
$SMTP_ADMIN_ADDRESS = Get-EnvVariable "SMTP_ADMIN_ADDRESS"
$AZURE_KEY_VAULT_URL = Get-EnvVariable "AZURE_KEY_VAULT_URL"
$AZURE_STORAGE_CONNECTION_STRING = Get-EnvVariable "AZURE_STORAGE_CONNECTION_STRING"
$DB_NAME = Get-EnvVariable "DB_NAME"
$DB_ROOT_USERNAME = Get-EnvVariable "DB_ROOT_USERNAME"
$DB_ROOT_PASSWORD = Get-EnvVariable "DB_ROOT_PASSWORD"
$DB_CONNECTION_STRING = Get-EnvVariable "DB_CONNECTION_STRING"

# Validate that all required secrets are present
$missingSecrets = @()
if ([string]::IsNullOrEmpty($BOERSENMEDIEN_USERNAME)) { $missingSecrets += "BOERSENMEDIEN_USERNAME" }
if ([string]::IsNullOrEmpty($BOERSENMEDIEN_PASSWORD)) { $missingSecrets += "BOERSENMEDIEN_PASSWORD" }
if ([string]::IsNullOrEmpty($ONEDRIVE_CLIENT_ID)) { $missingSecrets += "ONEDRIVE_CLIENT_ID" }
if ([string]::IsNullOrEmpty($ONEDRIVE_CLIENT_SECRET)) { $missingSecrets += "ONEDRIVE_CLIENT_SECRET" }
if ([string]::IsNullOrEmpty($ONEDRIVE_REFRESH_TOKEN)) { $missingSecrets += "ONEDRIVE_REFRESH_TOKEN" }
if ([string]::IsNullOrEmpty($SMTP_USERNAME)) { $missingSecrets += "SMTP_USERNAME" }
if ([string]::IsNullOrEmpty($SMTP_PASSWORD)) { $missingSecrets += "SMTP_PASSWORD" }
if ([string]::IsNullOrEmpty($SMTP_ADMIN_ADDRESS)) { $missingSecrets += "SMTP_ADMIN_ADDRESS" }
if ([string]::IsNullOrEmpty($DB_CONNECTION_STRING)) { $missingSecrets += "DB_CONNECTION_STRING" }
# SMTP_RECIPIENTS is optional (managed in MongoDB)

if ($missingSecrets.Count -gt 0) {
    Write-Host "❌ Error: Missing required secrets in .env file:" -ForegroundColor Red
    foreach ($secret in $missingSecrets) {
        Write-Host "  - $secret" -ForegroundColor Red
    }
    exit 1
}

Write-Host "✅ All required secrets found in .env file" -ForegroundColor Green

Write-Host "🚀 Deploying depot-butler to Azure Container Apps..." -ForegroundColor Green

# Get storage account key
Write-Host "📦 Getting storage account key..." -ForegroundColor Cyan
$STORAGE_KEY = az storage account keys list `
  --resource-group $RESOURCE_GROUP `
  --account-name $STORAGE_ACCOUNT `
  --query "[0].value" `
  --output tsv

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to get storage account key" -ForegroundColor Red
    exit 1
}

# Create Container App Job
Write-Host "🔧 Creating Container App Job..." -ForegroundColor Cyan
# Note: --replica-retry-limit is set to 0 to prevent duplicate notifications.
# Authentication/configuration failures won't be resolved by immediate retry.
# Transient errors (network timeouts, etc.) are handled at the application level.
az containerapp job create `
  --name $JOB_NAME `
  --resource-group $RESOURCE_GROUP `
  --environment $ENVIRONMENT `
  --trigger-type "Schedule" `
  --cron-expression "0 15 * * 1-5" `
  --replica-timeout 1800 `
  --replica-retry-limit 0 `
  --parallelism 1 `
  --replica-completion-count 1 `
  --image "ghcr.io/stefanfries/depot-butler:latest" `
  --cpu 1.0 `
  --memory 2.0Gi `
  --env-vars `
    "BOERSENMEDIEN_BASE_URL=$BOERSENMEDIEN_BASE_URL" `
    "BOERSENMEDIEN_LOGIN_URL=$BOERSENMEDIEN_LOGIN_URL" `
    "BOERSENMEDIEN_USERNAME=secretref:boersenmedien-username" `
    "BOERSENMEDIEN_PASSWORD=secretref:boersenmedien-password" `
    "ONEDRIVE_CLIENT_ID=secretref:onedrive-client-id" `
    "ONEDRIVE_CLIENT_SECRET=secretref:onedrive-client-secret" `
    "ONEDRIVE_REFRESH_TOKEN=secretref:onedrive-refresh-token" `
    "ONEDRIVE_ORGANIZE_BY_YEAR=true" `
    "ONEDRIVE_OVERWRITE_FILES=true" `
    "SMTP_SERVER=smtp.gmx.net" `
    "SMTP_PORT=587" `
    "SMTP_USERNAME=secretref:smtp-username" `
    "SMTP_PASSWORD=secretref:smtp-password" `
    "SMTP_ADMIN_ADDRESS=secretref:smtp-admin-address" `
    "TRACKING_ENABLED=true" `
    "TRACKING_RETENTION_DAYS=90" `
    "TRACKING_TEMP_DIR=/mnt/data/tmp" `
    "AZURE_KEY_VAULT_URL=$AZURE_KEY_VAULT_URL" `
    "AZURE_STORAGE_CONNECTION_STRING=secretref:azure-storage-connection-string" `
    "DISCOVERY_ENABLED=true" `
    "DB_NAME=$DB_NAME" `
    "DB_ROOT_USERNAME=secretref:db-root-username" `
    "DB_ROOT_PASSWORD=secretref:db-root-password" `
    "DB_CONNECTION_STRING=secretref:db-connection-string" `
  --secrets `
    "boersenmedien-username=$BOERSENMEDIEN_USERNAME" `
    "boersenmedien-password=$BOERSENMEDIEN_PASSWORD" `
    "onedrive-client-id=$ONEDRIVE_CLIENT_ID" `
    "onedrive-client-secret=$ONEDRIVE_CLIENT_SECRET" `
    "onedrive-refresh-token=$ONEDRIVE_REFRESH_TOKEN" `
    "smtp-username=$SMTP_USERNAME" `
    "smtp-password=$SMTP_PASSWORD" `
    "smtp-admin-address=$SMTP_ADMIN_ADDRESS" `
    "azure-storage-connection-string=$AZURE_STORAGE_CONNECTION_STRING" `
    "db-root-username=$DB_ROOT_USERNAME" `
    "db-root-password=$DB_ROOT_PASSWORD" `
    "db-connection-string=$DB_CONNECTION_STRING"

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to create Container App Job" -ForegroundColor Red
    exit 1
}

# Create storage mount (if not exists)
Write-Host "🔗 Creating storage mount..." -ForegroundColor Cyan
az containerapp env storage set `
  --name $ENVIRONMENT `
  --resource-group $RESOURCE_GROUP `
  --storage-name "depot-data-storage" `
  --azure-file-account-name $STORAGE_ACCOUNT_NAME `
  --azure-file-account-key $STORAGE_KEY `
  --azure-file-share-name "depot-butler-data" `
  --access-mode ReadWrite

if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️  Warning: Storage mount may already exist" -ForegroundColor Yellow
}

# Add volume mount to job
Write-Host "📦 Adding volume mount to job..." -ForegroundColor Cyan
az containerapp job update `
  --name $JOB_NAME `
  --resource-group $RESOURCE_GROUP `
  --set "properties.template.volumes[0].name=data-volume" `
  --set "properties.template.volumes[0].storageType=AzureFile" `
  --set "properties.template.volumes[0].storageName=depot-data-storage" `
  --set "properties.template.containers[0].volumeMounts[0].volumeName=data-volume" `
  --set "properties.template.containers[0].volumeMounts[0].mountPath=/mnt/data"

if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️  Warning: Failed to add volume mount - may need manual configuration" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "✅ Deployment complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Next steps:" -ForegroundColor Cyan
Write-Host "  1. Verify job in Azure Portal: https://portal.azure.com/#@/resource/subscriptions/.../resourceGroups/$RESOURCE_GROUP/providers/Microsoft.App/jobs/$JOB_NAME"
Write-Host "  2. Test manual run: az containerapp job start --name $JOB_NAME --resource-group $RESOURCE_GROUP"
Write-Host "  3. Check logs: az containerapp job logs show --name $JOB_NAME --resource-group $RESOURCE_GROUP --container $JOB_NAME"
Write-Host ""
Write-Host "⏰ Scheduled to run: Monday-Friday at 3:00 PM UTC (4:00 PM German winter time)" -ForegroundColor Green
Write-Host "⚠️  Remember to update cron expression for summer time changes (see TIMEZONE_REMINDERS.md)" -ForegroundColor Yellow
