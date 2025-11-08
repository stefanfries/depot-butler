
# depot-butler

Automated tool to download the latest financial reports from Börsenmedien subscriptions, store them in OneDrive, and email them to recipients.

## 🚀 Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/stefanfries/depot-butler.git
   cd depot-butler
   ```

2. **Set up environment**
   ```bash
   # Copy environment template
   cp .env.example .env
   
   # Edit .env and fill in your credentials
   # See ONEDRIVE_SETUP.md for OneDrive OAuth setup
   ```

3. **Install dependencies**
   ```bash
   pip install uv
   uv sync
   ```

4. **Set up OneDrive authentication**
   ```bash
   # Run interactive OAuth setup
   python setup_onedrive_auth.py
   
   # Copy the refresh token to your .env file
   ```

5. **Test locally**
   ```bash
   # Download latest edition
   uv run python -m depotbutler download
   
   # Full workflow (download + OneDrive + email)
   uv run python -m depotbutler full
   ```

6. **Deploy to Azure** (optional)
   ```bash
   # See DEPLOYMENT.md for complete guide
   .\deploy-to-azure.ps1
   ```

## 📚 Documentation

- [**DEPLOYMENT.md**](./DEPLOYMENT.md) - Azure Container Apps deployment guide
- [**ONEDRIVE_SETUP.md**](./ONEDRIVE_SETUP.md) - OneDrive OAuth configuration
- [**TIMEZONE_REMINDERS.md**](./TIMEZONE_REMINDERS.md) - Seasonal cron adjustments

## ✨ Features

- 🔄 Automatic subscription discovery from Börsenmedien account
- 📥 Downloads latest financial report editions
- ☁️ Uploads to OneDrive with year-based organization
- 📧 Sends email notifications to multiple recipients
- 🚫 Prevents duplicate processing with persistent tracking
- ⏰ Runs on schedule in Azure Container Apps (weekdays at 4 PM German time)
- 🧹 Auto-cleanup of old tracking records

## 🔧 Configuration

All configuration is managed through the `.env` file. Key settings:

```bash
# Börsenmedien Credentials
BOERSENMEDIEN_USERNAME=your.email@example.com
BOERSENMEDIEN_PASSWORD=your_password

# OneDrive OAuth
ONEDRIVE_CLIENT_ID=your_client_id
ONEDRIVE_CLIENT_SECRET=your_client_secret
ONEDRIVE_REFRESH_TOKEN=your_refresh_token

# SMTP Email
SMTP_USERNAME=your.email@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_RECIPIENTS=["recipient1@example.com","recipient2@example.com"]
```

See `.env.example` for complete configuration options.

## 🛡️ Security

- ✅ `.env` file is in `.gitignore` (never committed)
- ✅ Use `.env.example` as template for new setups
- ✅ Azure secrets managed via deployment script
- ✅ Supports Azure Key Vault for enhanced security

## 📝 License

See [LICENSE](./LICENSE) file for details.
