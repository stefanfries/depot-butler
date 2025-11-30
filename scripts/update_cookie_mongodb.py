"""
Script to update the authentication cookie in MongoDB.

Simply paste your .AspNetCore.Cookies value when prompted.

Usage:
    uv run python scripts/update_cookie_mongodb.py
"""

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from depotbutler.db.mongodb import get_mongodb_service
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


async def update_cookie():
    """Update the authentication cookie in MongoDB."""
    print("=" * 70)
    print("MongoDB Cookie Update Tool")
    print("=" * 70)
    print()
    print("This script will update the authentication cookie in MongoDB.")
    print()
    print("Instructions:")
    print("1. Login to https://konto.boersenmedien.com in your browser")
    print("2. Open Developer Tools (F12)")
    print("3. Go to Application/Storage > Cookies")
    print("4. Find .AspNetCore.Cookies and copy its Value")
    print("5. Paste it below")
    print()
    print("=" * 70)
    print()

    # Get cookie value from user
    cookie_value = input("Paste cookie value here: ").strip()

    if not cookie_value:
        print("❌ Error: No cookie value provided")
        return False

    # Try to get expiration from local file if available
    expires_at = None
    cookie_file = Path("data/browser_cookies.json")
    if cookie_file.exists():
        try:
            with open(cookie_file, "r") as f:
                cookie_data = json.load(f)
                if isinstance(cookie_data, list):
                    cookie_data = cookie_data[0] if cookie_data else {}
                expires_unix = cookie_data.get("expires")
                if expires_unix:
                    expires_at = datetime.fromtimestamp(expires_unix, tz=timezone.utc)
                    print(f"Found expiration date: {expires_at}")
        except Exception as e:
            logger.warning(f"Could not read expiration from local file: {e}")

    # Get optional username
    updated_by = input("Your name/username (optional, press Enter to skip): ").strip()
    if not updated_by:
        updated_by = "manual-update"

    print()
    print("Connecting to MongoDB...")

    try:
        # Get MongoDB service
        mongodb = await get_mongodb_service()

        # Update the cookie
        print("Updating cookie in MongoDB...")
        success = await mongodb.update_auth_cookie(cookie_value, expires_at, updated_by)

        if success:
            print()
            print("=" * 70)
            print("✅ SUCCESS!")
            print("=" * 70)
            print()
            print(f"Cookie updated in MongoDB (length: {len(cookie_value)} characters)")
            print(f"Updated by: {updated_by}")
            if expires_at:
                days_until_expiry = (expires_at - datetime.now(timezone.utc)).days
                print(f"Expires on: {expires_at} ({days_until_expiry} days)")
            print()
            print("The cookie will now be used by depot-butler in both")
            print("local and Azure environments.")
            print()
            return True
        else:
            print()
            print("❌ Failed to update cookie in MongoDB")
            print("Check the logs above for error details")
            return False

    except Exception as e:
        print()
        print(f"❌ Error: {e}")
        logger.error(f"Failed to update cookie: {e}")
        return False


async def verify_cookie():
    """Verify the current cookie in MongoDB."""
    print()
    print("=" * 70)
    print("Verifying current cookie in MongoDB...")
    print("=" * 70)
    print()

    try:
        mongodb = await get_mongodb_service()
        cookie_value = await mongodb.get_auth_cookie()

        if cookie_value:
            print(f"✓ Cookie found in MongoDB")
            print(f"  Length: {len(cookie_value)} characters")
            print(f"  Preview: {cookie_value[:50]}...")
            return True
        else:
            print("⚠️  No cookie found in MongoDB")
            return False

    except Exception as e:
        print(f"❌ Error verifying cookie: {e}")
        return False


async def main():
    """Main entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        # Just verify the current cookie
        await verify_cookie()
        return

    # Update the cookie
    success = await update_cookie()

    if success:
        # Verify it was saved correctly
        await verify_cookie()

    print()
    print("=" * 70)
    print()


if __name__ == "__main__":
    asyncio.run(main())
