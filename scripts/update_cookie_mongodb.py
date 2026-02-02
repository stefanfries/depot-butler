"""
Script to update the authentication cookie in MongoDB.

Simply paste your .AspNetCore.Cookies value when prompted.

Usage:
    uv run python scripts/update_cookie_mongodb.py
"""

import asyncio
import sys
from datetime import UTC, datetime, timedelta

from depotbutler.db.mongodb import get_mongodb_service
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


async def update_cookie() -> bool:
    """Update the authentication cookie in MongoDB."""
    print("=" * 70)
    print("MongoDB Cookie Update Tool")
    print("=" * 70)
    print()
    print("This script will update the authentication cookie in MongoDB.")
    print()
    print("Instructions:")
    print("1. Login to https://konto.boersenmedien.com in your browser")
    print("   (Use incognito/private window for a fresh session)")
    print("2. Open Developer Tools (F12)")
    print("3. Go to Application/Storage > Cookies")
    print("4. Click on .AspNetCore.Cookies")
    print("5. Copy the 'Value' field (the long encrypted string)")
    print()
    print("=" * 70)
    print()

    # Get cookie value from user
    cookie_value = input("Paste cookie value here: ").strip()

    if not cookie_value:
        print("❌ Error: No cookie value provided")
        return False

    # Handle expiration date
    print()
    print("ℹ️  Note: .AspNetCore.Cookies shows 'No Expiration' in browser DevTools")
    print("   because it's a session cookie, but the server has an expiration")
    print("   encoded inside the encrypted value.")
    print()
    print("You can either:")
    print("  1. Press Enter to use a default 7-day expiration")
    print("  2. Enter a specific date if you know when it expires")
    print()
    expires_input = input(
        "Expiration date (YYYY-MM-DD HH:MM:SS) or press Enter for 7 days: "
    ).strip()

    expires_at = None
    if expires_input:
        try:
            # Try parsing with time first
            if " " in expires_input:
                expires_at = datetime.strptime(
                    expires_input, "%Y-%m-%d %H:%M:%S"
                ).replace(tzinfo=UTC)
            else:
                # Just date, assume end of day
                expires_at = datetime.strptime(expires_input, "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59, tzinfo=UTC
                )
            print(f"✓ Using expiration date: {expires_at}")
        except ValueError as e:
            print(f"⚠️  Could not parse date: {e}")
            expires_at = datetime.now(UTC) + timedelta(days=7)
            print(f"✓ Using default 7-day expiration: {expires_at}")
    else:
        expires_at = datetime.now(UTC) + timedelta(days=7)
        print(f"✓ Using default 7-day expiration: {expires_at}")

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
                days_until_expiry = (expires_at - datetime.now(UTC)).days
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


async def verify_cookie() -> bool:
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
            print("✓ Cookie found in MongoDB")
            print(f"  Length: {len(cookie_value)} characters")
            print(f"  Preview: {cookie_value[:50]}...")
            return True
        else:
            print("⚠️  No cookie found in MongoDB")
            return False

    except Exception as e:
        print(f"❌ Error verifying cookie: {e}")
        return False


async def main() -> None:
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
