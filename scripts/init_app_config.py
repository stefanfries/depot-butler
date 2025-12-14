"""
Initialize application configuration in MongoDB.

This script sets up the default app_config document with initial values.
Run this once to migrate from .env-only to MongoDB config storage.

Usage:
    $env:PYTHONPATH="src" ; uv run python scripts/init_app_config.py
"""

import asyncio
import sys

from depotbutler.db.mongodb import get_mongodb_service
from depotbutler.settings import Settings


async def init_config():
    """Initialize app configuration in MongoDB."""
    print("=" * 70)
    print("MongoDB App Configuration Initialization")
    print("=" * 70)
    print()
    print("This script will create/update the app_config document in MongoDB")
    print("with default values from your .env file.")
    print()

    try:
        # Load current settings from .env
        settings = Settings()

        # Get current admin email from .env
        admin_email = str(settings.mail.admin_address)

        print(f"Current admin email from .env: {admin_email}")
        print()

        # Connect to MongoDB
        print("Connecting to MongoDB...")
        mongodb = await get_mongodb_service()

        # Check if config already exists
        existing_config = await mongodb.db.config.find_one({"_id": "app_config"})

        if existing_config:
            print("⚠️  app_config document already exists:")
            print(f"   - log_level: {existing_config.get('log_level', 'not set')}")
            print(
                f"   - cookie_warning_days: {existing_config.get('cookie_warning_days', 'not set')}"
            )
            if "onedrive_base_folder_path" in existing_config:
                print(
                    "   - Note: onedrive_base_folder_path (obsolete) - folder paths are now per publication"
                )
            print(
                f"   - onedrive_organize_by_year: {existing_config.get('onedrive_organize_by_year', 'not set')}"
            )
            print(
                f"   - tracking_enabled: {existing_config.get('tracking_enabled', 'not set')}"
            )
            print(
                f"   - tracking_retention_days: {existing_config.get('tracking_retention_days', 'not set')}"
            )
            print(f"   - smtp_server: {existing_config.get('smtp_server', 'not set')}")
            print(f"   - smtp_port: {existing_config.get('smtp_port', 'not set')}")
            print()
            response = input("Overwrite with defaults? (yes/no): ").strip().lower()
            if response not in ["yes", "y"]:
                print("Cancelled. No changes made.")
                return

        # Default configuration
        config = {
            "log_level": "INFO",  # Can be changed to DEBUG, WARNING, ERROR
            "cookie_warning_days": 5,  # Days before expiration to send warning
            "admin_emails": [admin_email],  # List of admin email addresses
            # OneDrive settings (Note: folder paths are now per-publication)
            "onedrive_organize_by_year": settings.onedrive.organize_by_year,
            # Tracking settings
            "tracking_enabled": settings.tracking.enabled,
            "tracking_retention_days": settings.tracking.retention_days,
            # SMTP settings
            "smtp_server": settings.mail.server,
            "smtp_port": settings.mail.port,
        }

        print()
        print("Setting up configuration...")
        print(f"  - log_level: {config['log_level']}")
        print(f"  - cookie_warning_days: {config['cookie_warning_days']}")
        print(f"  - admin_emails: {config['admin_emails']}")
        print("  - OneDrive: folder paths configured per publication in MongoDB")
        print(f"  - onedrive_organize_by_year: {config['onedrive_organize_by_year']}")
        print(f"  - tracking_enabled: {config['tracking_enabled']}")
        print(f"  - tracking_retention_days: {config['tracking_retention_days']}")
        print(f"  - smtp_server: {config['smtp_server']}")
        print(f"  - smtp_port: {config['smtp_port']}")
        print()

        # Update MongoDB
        success = await mongodb.update_app_config(config)

        if success:
            print("=" * 70)
            print("✅ SUCCESS!")
            print("=" * 70)
            print()
            print("App configuration initialized in MongoDB:")
            print()
            print("To change settings:")
            print("  1. Use MongoDB Compass or mongosh")
            print("  2. Navigate to the 'config' collection")
            print("  3. Edit the 'app_config' document")
            print()
            print("Example changes:")
            print("  - Set log_level to 'DEBUG' for verbose logging")
            print("  - Adjust cookie_warning_days (currently 5)")
            print("  - Add more admin emails to the admin_emails array")
            print("  - Change OneDrive folder path or organization")
            print("  - Adjust tracking retention period")
            print("  - Switch SMTP server/port for different email provider")
            print()
            print("Changes take effect on next workflow run (no deployment needed!)")
            print()
        else:
            print("❌ Failed to initialize configuration")
            print("Check logs for details")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(init_config())
