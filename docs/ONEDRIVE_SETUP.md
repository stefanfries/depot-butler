# 🚀 OneDrive Integration Setup Guide

This guide walks you through setting up OneDrive integration for DepotButler, optimized for Azure Container deployment.

## 📋 Prerequisites

- ✅ Azure account with access to Azure Portal
- ✅ Microsoft 365 or personal OneDrive account
- ✅ DepotButler project with dependencies installed

## 🔧 Step 1: Azure App Registration

### 1.1 Register Application in Azure Portal

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Azure Active Directory** > **App registrations**
3. Click **New registration**
4. Fill in application details:
   - **Name**: `DepotButler-OneDrive`
   - **Supported account types**: `Accounts in any organizational directory and personal Microsoft accounts`
   - **Redirect URI**: `Web` → `http://localhost:8080`
5. Click **Register**

### 1.2 Configure API Permissions

1. In your app registration, go to **API permissions**
2. Click **Add a permission**
3. Select **Microsoft Graph**
4. Choose **Delegated permissions**
5. Add permission: `Files.ReadWrite.All`
6. Click **Grant admin consent** (if you're admin) or ask admin to approve

### 1.3 Create Client Secret

1. Go to **Certificates & secrets**
2. Click **New client secret**
3. Add description: `DepotButler Container Secret`
4. Set expiration: `24 months` (recommended)
5. Click **Add**
6. **⚠️ IMPORTANT**: Copy the secret value immediately (you won't see it again)

### 1.4 Note Required Information

Copy these values from your app registration:

- **Application (client) ID**: Found on Overview page
- **Directory (tenant) ID**: Found on Overview page  
- **Client secret**: From step 1.3

## 🔧 Step 2: Local Configuration

### 2.1 Update Environment Variables

Update your `.env` file (copy from `.env.example` if needed):

```bash
# OneDrive OAuth2 Configuration
ONEDRIVE_CLIENT_ID=your_actual_client_id_here
ONEDRIVE_CLIENT_SECRET=your_actual_client_secret_here
ONEDRIVE_REFRESH_TOKEN=  # Will be filled after Step 3

# OneDrive Upload Settings
# Note: Folder paths are configured per publication in MongoDB
ONEDRIVE_ORGANIZE_BY_YEAR=true
ONEDRIVE_OVERWRITE_FILES=true
```

## 🔧 Step 3: Initial Authentication (Local)

### 3.1 Run OAuth Setup Script

```bash
# From project root directory
uv run python setup_onedrive_auth.py
```

### 3.2 Follow Interactive Prompts

1. Script will display an authorization URL
2. Open URL in browser and log in with your Microsoft account
3. Grant permissions to the application
4. Copy the redirect URL from browser (even if it shows error page)
5. Paste URL back into the script
6. Script will generate refresh token

### 3.3 Save Refresh Token

The script will output something like:

```bash
ONEDRIVE_REFRESH_TOKEN=0.AQcAkg...very_long_token...XYZ
```

**⚠️ SECURITY**: Keep this token secure! It provides access to your OneDrive.

## 🔧 Step 4: Azure Container Configuration

### 4.1 Environment Variables for Container

The deployment script (`deploy-to-azure.ps1`) automatically reads all configuration from your `.env` file, including:

```bash
# OneDrive OAuth (required)
ONEDRIVE_CLIENT_ID=your_client_id
ONEDRIVE_CLIENT_SECRET=your_client_secret
ONEDRIVE_REFRESH_TOKEN=your_refresh_token_from_step_3

# OneDrive Upload Settings
# Note: Folder paths are configured per publication in MongoDB
ONEDRIVE_ORGANIZE_BY_YEAR=true
ONEDRIVE_OVERWRITE_FILES=true
```

Simply run `.\deploy-to-azure.ps1` and it will configure everything automatically.

### 4.2 Optional: Azure Key Vault (Enhanced Security)

For production deployments, consider storing secrets in Azure Key Vault:

1. Create Azure Key Vault
2. Store `onedrive-refresh-token` as secret
3. Enable Managed Identity on your Container Instance
4. Grant Container access to Key Vault
5. Set environment variable: `AZURE_KEY_VAULT_URL=https://your-vault.vault.azure.net/`

## 🧪 Step 5: Testing

### 5.1 Test Locally

```bash
# Test download only
uv run python -m depotbutler download

# Test full workflow (download + OneDrive + email)
uv run python -m depotbutler full
```

### 5.2 Test OneDrive Integration

```bash
# Test OneDrive authentication separately
uv run python -c "
import asyncio
from depotbutler.onedrive import OneDriveService

async def test():
    service = OneDriveService()
    success = await service.authenticate()
    print(f'Authentication: {\"✅ Success\" if success else \"❌ Failed\"}')
    if success:
        # List files in root of configured folder
        files = await service.list_files()
        print(f'Files in OneDrive folder: {len(files)}')
    await service.close()

asyncio.run(test())
"
```

## 🚀 Step 6: Azure Container Deployment

### 6.1 Container Image

Build container with your updated code:

```dockerfile
FROM python:3.13-slim

WORKDIR /app
COPY . /app

# Install uv and dependencies
RUN pip install uv
RUN uv sync

# Set entry point
CMD ["uv", "run", "python", "-m", "depotbutler", "full"]
```

### 6.2 Azure Container Instance

Deploy with environment variables from Step 4.1:

```bash
az container create \
  --resource-group your-rg \
  --name depot-butler \
  --image your-registry/depot-butler:latest \
  --restart-policy Never \
  --environment-variables \
    ONEDRIVE_CLIENT_ID="your_client_id" \
    ONEDRIVE_CLIENT_SECRET="your_client_secret" \
    ONEDRIVE_REFRESH_TOKEN="your_refresh_token" \
    ONEDRIVE_ORGANIZE_BY_YEAR="true" \
    ONEDRIVE_OVERWRITE_FILES="true" \
    # Note: Folder paths are configured per publication in MongoDB
    # ... other environment variables
```

### 6.3 Scheduled Execution

Set up Azure Logic Apps or Azure Functions to trigger container weekly:

1. Create Logic App with recurrence trigger (weekly)
2. Add action to start Container Instance
3. Configure error handling and notifications

## 📊 Verification

After successful setup:

1. ✅ Container authenticates with OneDrive automatically
2. ✅ Files are uploaded to configured OneDrive folder path
3. ✅ Files are organized by year if ONEDRIVE_ORGANIZE_BY_YEAR is enabled
4. ✅ Existing files are overwritten (as configured)
5. ✅ Email notifications are sent on success/failure
6. ✅ Container runs on schedule via Azure scheduling

## 🛡️ Security Best Practices

- 🔐 Never commit refresh tokens to git
- 🔄 Rotate client secrets regularly (before expiration)
- 📝 Use Azure Key Vault for production secrets
- 🚫 Limit API permissions to minimum required
- 📊 Monitor authentication logs in Azure

## ⚡ Performance Optimization

### Chunked Upload for Large Files

DepotButler automatically optimizes uploads for large files (>4MB) using OneDrive's upload session API:

**Configuration:**

- **Threshold**: Files larger than 4MB use chunked upload
- **Chunk Size**: 10MB per chunk (optimized for speed)
- **Timeout**: 120 seconds per chunk
- **Max Chunk Size**: Up to 60MB supported by OneDrive API

**Performance Benefits:**

- **28x faster** than simple uploads for large files
- Example: 64MB file uploads in ~9 seconds (vs 4.5 minutes with simple upload)
- More reliable for large publications (prevents timeouts)
- Automatic retry and progress tracking per chunk

**How It Works:**

1. Files >4MB trigger chunked upload automatically
2. File is split into 10MB chunks
3. Each chunk is uploaded sequentially with progress logging
4. OneDrive API assembles chunks into final file

**Example Log Output:**

```text
Uploading file: 2025-12-10_Der-Aktionär-Edition_01-26.pdf (63734533 bytes)
Using chunked upload for large file
Uploading 63734533 bytes in 7 chunks of 10485760 bytes
Uploading chunk 1/7 (0-10485759/63734533)
Uploading chunk 2/7 (10485760-20971519/63734533)
...
Successfully uploaded to OneDrive
```

**No Configuration Required:** The optimization is automatic and enabled by default.

### Filename Format

Files are automatically renamed for consistency and readability:

**Format:** `{date}_{Title-Cased-Title}_{issue}.pdf`

**Rules:**

- Publication date in ISO format: `YYYY-MM-DD`
- Title converted to title case (e.g., "DER AKTIONÄR" → "Der Aktionär")
- Spaces in title replaced with hyphens
- Issue number separated with underscore
- Forward slashes in issue number replaced with hyphens

**Examples:**

- Input: `"DER AKTIONÄR EDITION 01/26"` → `2025-12-10_Der-Aktionär-Edition_01-26.pdf`
- Input: `"Megatrend Folger 50/2025"` → `2025-12-11_Megatrend-Folger_50-2025.pdf`

**Benefits:**

- Consistent naming across all publications
- Filesystem-safe (Windows, macOS, Linux)
- Sortable by date (ISO format)
- Readable and professional appearance

## 🐛 Troubleshooting

### Authentication Issues

- Verify client ID, secret, and tenant ID are correct
- Check if refresh token has expired (refresh tokens can expire)
- Ensure API permissions are granted and consented

### Upload Issues

- Verify OneDrive folder permissions
- Check file size limits (OneDrive has limits)
- Monitor Azure Container logs for detailed errors

### Container Issues

- Check environment variables are set correctly
- Verify container has internet access
- Monitor container resource usage

---

## 📞 Support

If you encounter issues:

1. Check container logs for detailed error messages
2. Verify all environment variables are set
3. Test authentication locally first
4. Check Azure service status

Your OneDrive integration is now ready for Azure Container deployment! 🎉
