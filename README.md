
# depot-butler

Automated tool to download the latest financial reports from Börsenmedien subscriptions, store them in OneDrive, and email them to recipients.

## ✨ Key Highlights

- 🚀 **Lightweight & Fast**: HTTPX-based HTTP client (no browser overhead)
- � **Multi-Publication Support**: Processes all active publications in single run
- 🔐 **Cookie Authentication**: Simple 3-day manual cookie refresh cycle
- ☁️ **Small Docker Image**: ~200MB (no browser dependencies)
- 💰 **Cost Efficient**: Lower Azure resource usage (CPU/memory)
- 🗄️ **Database-Driven**: Publications managed in MongoDB with automatic metadata extraction
- 🧪 **Well Tested**: 180 passing tests with >85% coverage

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
   # Test recipient filtering (no side effects)
   python scripts/test_recipient_filtering.py
   
   # Dry-run mode (simulates workflow without sending emails/uploads)
   python scripts/test_dry_run.py
   # or: python -m depotbutler.main full --dry-run
   
   # Download only (for testing)
   uv run python -m depotbutler download
   
   # Full workflow (download + OneDrive + email)
   uv run python -m depotbutler full
   ```

6. **Initialize MongoDB Configuration**

   ```bash
   # Set up dynamic configuration (log level, admin emails, etc.)
   $env:PYTHONPATH="src"
   uv run python scripts/init_app_config.py
   ```

7. **Seed Publications Collection**

   ```bash
   # Discover subscriptions and populate MongoDB with metadata
   $env:PYTHONPATH="src"
   uv run python scripts/seed_publications.py
   ```

8. **Deploy to Azure** (optional)

   ```bash
   # See DEPLOYMENT.md for complete guide
   .\deploy-to-azure.ps1
   ```

## 📚 Documentation

- [**CONFIGURATION.md**](./docs/CONFIGURATION.md) - Dynamic configuration via MongoDB
- [**MONGODB.md**](./docs/MONGODB.md) - MongoDB setup and data management
- [**DRY_RUN_MODE.md**](./docs/DRY_RUN_MODE.md) - **NEW!** Testing without side effects
- [**DEPLOYMENT.md**](./docs/DEPLOYMENT.md) - Azure Container Apps deployment guide
- [**ONEDRIVE_SETUP.md**](./docs/ONEDRIVE_SETUP.md) - OneDrive OAuth configuration
- [**COOKIE_AUTHENTICATION.md**](./docs/COOKIE_AUTHENTICATION.md) - Cookie management
- [**TIMEZONE_REMINDERS.md**](./docs/TIMEZONE_REMINDERS.md) - Seasonal cron adjustments

## ✨ Features

- 🚀 **HTTPX-Based Client**: Lightweight HTTP requests (no browser needed)
- 🔐 **Cookie Authentication**: Simple manual cookie export every 3 days
- 🔄 **Automatic Subscription Discovery**: Extracts metadata (Abo-Art, Laufzeit, dates) from account
- 🗄️ **Database-Driven Publications**: Publications managed in MongoDB with automatic metadata
- � **Recipient Preferences**: Per-publication email and OneDrive delivery settings
- � **Multi-Publication Processing**: Processes all active publications in single workflow run
- 📥 Downloads latest financial report editions
- ☁️ Uploads to OneDrive with customizable folder paths per recipient
- 📧 Sends email notifications to filtered recipients
- 📊 **Consolidated Notifications**: Single summary email with status of all publications
- 🚫 Prevents duplicate processing with persistent tracking per publication
- ⏰ Runs on schedule in Azure Container Apps (weekdays at 4 PM German time)
- 🧹 Auto-cleanup of old tracking records
- ⚙️ Dynamic configuration via MongoDB (no redeployment needed)
- 🧪 **Dry-Run Mode**: Test workflow without sending emails or uploading files
- 📦 **Small Docker Image**: ~200MB (no browser/webkit dependencies)
- 💰 **Cost Efficient**: 60-70% lower Azure resource usage vs browser automation

## 🔧 Configuration

Configuration uses a hybrid approach:

### Environment Variables (.env)

Secrets and bootstrap settings:

```bash
# Börsenmedien Credentials
BOERSENMEDIEN_USERNAME=your.email@example.com
BOERSENMEDIEN_PASSWORD=your_password

# MongoDB Connection
DB_CONNECTION_STRING=mongodb+srv://...

# OneDrive OAuth
ONEDRIVE_CLIENT_ID=your_client_id
ONEDRIVE_CLIENT_SECRET=your_client_secret
ONEDRIVE_REFRESH_TOKEN=your_refresh_token

# SMTP Email
SMTP_SERVER=smtp.gmx.net
SMTP_USERNAME=your.email@example.com
SMTP_PASSWORD=your_app_password
SMTP_ADMIN_ADDRESS=admin@example.com
```

### MongoDB Dynamic Configuration

Settings you can change without redeployment:

- **`log_level`**: DEBUG, INFO, WARNING, ERROR
- **`cookie_warning_days`**: Days before expiration to warn (default: 5)
- **`admin_emails`**: List of admin email addresses

**Change settings:** Edit the `app_config` document in MongoDB  
**Takes effect:** Next workflow run (no redeployment!)

See [CONFIGURATION.md](./docs/CONFIGURATION.md) for detailed guide.

## 🛡️ Security

- ✅ `.env` file is in `.gitignore` (never committed)
- ✅ Use `.env.example` as template for new setups
- ✅ Azure secrets managed via deployment script
- ✅ MongoDB credentials separate from app config
- ✅ Dynamic settings stored in MongoDB (not in environment variables)

## 📝 License

See [LICENSE](./LICENSE) file for details.
