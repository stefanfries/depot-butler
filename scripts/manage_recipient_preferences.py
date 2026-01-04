"""
Admin tool for managing recipient publication preferences.

Usage:
    # Add publication preference to specific recipient
    uv run python scripts/manage_recipient_preferences.py add user@example.com megatrend-folger

    # Remove publication preference from recipient
    uv run python scripts/manage_recipient_preferences.py remove user@example.com megatrend-folger

    # List preferences for specific recipient
    uv run python scripts/manage_recipient_preferences.py list user@example.com

    # Add publication to ALL recipients (bulk operation)
    uv run python scripts/manage_recipient_preferences.py bulk-add megatrend-folger

    # Remove publication from ALL recipients (bulk operation)
    uv run python scripts/manage_recipient_preferences.py bulk-remove megatrend-folger

    # Show preference statistics across all recipients
    uv run python scripts/manage_recipient_preferences.py stats
"""

import argparse
import asyncio
import sys
from pathlib import Path

from depotbutler.db.mongodb import get_mongodb_service

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


async def add_preference(
    email: str,
    publication_id: str,
    email_enabled: bool = True,
    upload_enabled: bool = True,
) -> bool:
    """Add publication preference to specific recipient."""
    service = await get_mongodb_service()

    # Verify recipient exists
    recipient = await service.db.recipients.find_one({"email": email})
    if not recipient:
        print(f"❌ Recipient not found: {email}")
        await service.close()
        return False

    # Verify publication exists
    publication = await service.db.publications.find_one(
        {"publication_id": publication_id}
    )
    if not publication:
        print(f"❌ Publication not found: {publication_id}")
        await service.close()
        return False

    # Check if preference already exists
    existing_prefs = recipient.get("publication_preferences", [])
    if any(p.get("publication_id") == publication_id for p in existing_prefs):
        print(f"⚠️  Preference already exists for {email} → {publication_id}")
        print("Use MongoDB directly to update existing preference settings")
        await service.close()
        return False

    # Create new preference
    new_pref = {
        "publication_id": publication_id,
        "enabled": True,
        "email_enabled": email_enabled,
        "upload_enabled": upload_enabled,
        "custom_onedrive_folder": None,
        "organize_by_year": None,
        "send_count": 0,
        "last_sent_at": None,
    }

    # Add preference to recipient
    result = await service.db.recipients.update_one(
        {"email": email}, {"$push": {"publication_preferences": new_pref}}
    )

    if result.modified_count > 0:
        pub_name = publication["name"]
        print(f"✅ Added preference: {email} → {pub_name}")
        print(f"   Email: {'✓' if email_enabled else '✗'}")
        print(f"   Upload: {'✓' if upload_enabled else '✗'}")
        await service.close()
        return True
    else:
        print("❌ Failed to add preference")
        await service.close()
        return False


async def remove_preference(email: str, publication_id: str) -> bool:
    """Remove publication preference from specific recipient."""
    service = await get_mongodb_service()

    # Verify recipient exists
    recipient = await service.db.recipients.find_one({"email": email})
    if not recipient:
        print(f"❌ Recipient not found: {email}")
        await service.close()
        return False

    # Check if preference exists
    existing_prefs = recipient.get("publication_preferences", [])
    if not any(p.get("publication_id") == publication_id for p in existing_prefs):
        print(f"⚠️  Preference not found for {email} → {publication_id}")
        await service.close()
        return False

    # Remove preference
    result = await service.db.recipients.update_one(
        {"email": email},
        {"$pull": {"publication_preferences": {"publication_id": publication_id}}},
    )

    if result.modified_count > 0:
        print(f"✅ Removed preference: {email} ❌ {publication_id}")
        await service.close()
        return True
    else:
        print("❌ Failed to remove preference")
        await service.close()
        return False


async def list_preferences(email: str) -> None:
    """List all preferences for specific recipient."""
    service = await get_mongodb_service()

    recipient = await service.db.recipients.find_one({"email": email})
    if not recipient:
        print(f"❌ Recipient not found: {email}")
        await service.close()
        return

    # Get publications for display
    publications = await service.get_publications(active_only=False)
    pub_map = {p["publication_id"]: p["name"] for p in publications}

    name = f"{recipient.get('first_name', '')} {recipient.get('last_name', '')}".strip()
    status = "ACTIVE" if recipient.get("active", True) else "INACTIVE"

    print(f"\n📋 Preferences for: {email}")
    print(f"Name: {name}")
    print(f"Status: {status}")
    print(f"Total Deliveries: {recipient.get('send_count', 0)}")
    print(f"Last Sent: {recipient.get('last_sent_at', 'Never')}")
    print()

    prefs = recipient.get("publication_preferences", [])
    if not prefs:
        print("⚠️  No preferences configured")
        await service.close()
        return

    print(f"Publications ({len(prefs)}):")
    print("-" * 80)

    for pref in prefs:
        pub_id = pref.get("publication_id", "unknown")
        pub_name = pub_map.get(pub_id, pub_id)
        enabled = "✓ ENABLED" if pref.get("enabled", True) else "✗ DISABLED"
        email_icon = "📧 Email" if pref.get("email_enabled", True) else "   No Email"
        upload_icon = (
            "☁️  Upload" if pref.get("upload_enabled", True) else "   No Upload"
        )

        print(f"\n{pub_name} ({pub_id})")
        print(f"  Status: {enabled}")
        print(f"  Delivery: {email_icon} | {upload_icon}")
        print(f"  Sent: {pref.get('send_count', 0)} times")
        if pref.get("last_sent_at"):
            print(f"  Last: {pref['last_sent_at']}")
        if pref.get("custom_onedrive_folder"):
            print(f"  OneDrive: {pref['custom_onedrive_folder']}")

    print("-" * 80)
    await service.close()


async def bulk_add_preference(
    publication_id: str, email_enabled: bool = True, upload_enabled: bool = True
) -> bool:
    """Add publication preference to ALL recipients."""
    service = await get_mongodb_service()

    # Verify publication exists
    publication = await service.db.publications.find_one(
        {"publication_id": publication_id}
    )
    if not publication:
        print(f"❌ Publication not found: {publication_id}")
        await service.close()
        return False

    pub_name = publication["name"]

    # Get all active recipients
    recipients = await service.db.recipients.find({"active": True}).to_list(None)
    if not recipients:
        print("❌ No active recipients found")
        await service.close()
        return False

    print(f"\n📢 Bulk operation: Add '{pub_name}' to {len(recipients)} recipients")
    print(f"   Email: {'✓' if email_enabled else '✗'}")
    print(f"   Upload: {'✓' if upload_enabled else '✗'}")
    print("\nProcessing...")

    added = 0
    skipped = 0

    for recipient in recipients:
        email = recipient["email"]
        existing_prefs = recipient.get("publication_preferences", [])

        # Skip if preference already exists
        if any(p.get("publication_id") == publication_id for p in existing_prefs):
            print(f"  ⏭️  Skipped: {email} (already has preference)")
            skipped += 1
            continue

        # Create new preference
        new_pref = {
            "publication_id": publication_id,
            "enabled": True,
            "email_enabled": email_enabled,
            "upload_enabled": upload_enabled,
            "custom_onedrive_folder": None,
            "organize_by_year": None,
            "send_count": 0,
            "last_sent_at": None,
        }

        # Add preference
        result = await service.db.recipients.update_one(
            {"email": email}, {"$push": {"publication_preferences": new_pref}}
        )

        if result.modified_count > 0:
            print(f"  ✅ Added: {email}")
            added += 1
        else:
            print(f"  ❌ Failed: {email}")

    print("\n✅ Bulk operation complete")
    print(f"   Added: {added}")
    print(f"   Skipped: {skipped}")
    print(f"   Total: {len(recipients)}")

    await service.close()
    return True


async def bulk_remove_preference(publication_id: str) -> bool:
    """Remove publication preference from ALL recipients."""
    service = await get_mongodb_service()

    # Verify publication exists
    publication = await service.db.publications.find_one(
        {"publication_id": publication_id}
    )
    if not publication:
        print(f"❌ Publication not found: {publication_id}")
        await service.close()
        return False

    pub_name = publication["name"]

    # Get all recipients (active and inactive)
    recipients = await service.db.recipients.find({}).to_list(None)
    if not recipients:
        print("❌ No recipients found")
        await service.close()
        return False

    print(f"\n📢 Bulk operation: Remove '{pub_name}' from {len(recipients)} recipients")
    print("\nProcessing...")

    removed = 0
    not_found = 0

    for recipient in recipients:
        email = recipient["email"]
        existing_prefs = recipient.get("publication_preferences", [])

        # Skip if preference doesn't exist
        if not any(p.get("publication_id") == publication_id for p in existing_prefs):
            not_found += 1
            continue

        # Remove preference
        result = await service.db.recipients.update_one(
            {"email": email},
            {"$pull": {"publication_preferences": {"publication_id": publication_id}}},
        )

        if result.modified_count > 0:
            print(f"  ✅ Removed: {email}")
            removed += 1
        else:
            print(f"  ❌ Failed: {email}")

    print("\n✅ Bulk operation complete")
    print(f"   Removed: {removed}")
    print(f"   Not Found: {not_found}")
    print(f"   Total: {len(recipients)}")

    await service.close()
    return True


async def show_statistics() -> None:
    """Show preference statistics across all recipients."""
    service = await get_mongodb_service()

    # Get all recipients and publications
    recipients = await service.db.recipients.find({}).to_list(None)
    publications = await service.get_publications(active_only=False)

    if not recipients:
        print("❌ No recipients found")
        await service.close()
        return

    # Calculate statistics
    total_recipients = len(recipients)
    active_recipients = sum(1 for r in recipients if r.get("active", True))
    with_prefs = sum(1 for r in recipients if r.get("publication_preferences"))
    without_prefs = total_recipients - with_prefs

    print("\n" + "=" * 100)
    print("📊 PREFERENCE STATISTICS")
    print("=" * 100)
    print(f"Total Recipients: {total_recipients}")
    print(
        f"  Active: {active_recipients} ({active_recipients / total_recipients * 100:.1f}%)"
    )
    print(f"  Inactive: {total_recipients - active_recipients}")
    print()
    print(
        f"Recipients with Preferences: {with_prefs} ({with_prefs / total_recipients * 100:.1f}%)"
    )
    print(
        f"Recipients without Preferences: {without_prefs} ({without_prefs / total_recipients * 100:.1f}%)"
    )
    print("=" * 100)

    # Per-publication statistics
    print("\n📚 Per-Publication Coverage")
    print("-" * 100)
    print(
        f"{'Publication':<40} | {'Recipients':>11} | {'Email':>6} | {'Upload':>7} | Coverage"
    )
    print("-" * 100)

    for pub in publications:
        pub_id = pub["publication_id"]
        pub_name = pub["name"]

        # Count recipients with this preference
        recipients_with_pub = 0
        email_enabled_count = 0
        upload_enabled_count = 0

        for recipient in recipients:
            if not recipient.get("active", True):
                continue  # Only count active recipients

            prefs = recipient.get("publication_preferences", [])
            for pref in prefs:
                if pref.get("publication_id") == pub_id and pref.get("enabled", True):
                    recipients_with_pub += 1
                    if pref.get("email_enabled", True):
                        email_enabled_count += 1
                    if pref.get("upload_enabled", True):
                        upload_enabled_count += 1
                    break

        coverage = (
            f"{recipients_with_pub / active_recipients * 100:.1f}%"
            if active_recipients > 0
            else "0%"
        )

        status_icon = "✓" if pub.get("active", True) else "✗"
        pub_display = f"{status_icon} {pub_name}"

        print(
            f"{pub_display:<40} | {recipients_with_pub:>11} | {email_enabled_count:>6} | {upload_enabled_count:>7} | {coverage}"
        )

    print("-" * 100)

    # Delivery method statistics
    print("\n📧 Delivery Method Statistics")
    print("-" * 100)

    email_only = 0
    upload_only = 0
    both = 0
    neither = 0

    for recipient in recipients:
        if not recipient.get("active", True):
            continue

        prefs = recipient.get("publication_preferences", [])
        if not prefs:
            continue

        # Check if recipient has any email or upload enabled
        has_email = any(
            p.get("email_enabled", True) and p.get("enabled", True) for p in prefs
        )
        has_upload = any(
            p.get("upload_enabled", True) and p.get("enabled", True) for p in prefs
        )

        if has_email and has_upload:
            both += 1
        elif has_email:
            email_only += 1
        elif has_upload:
            upload_only += 1
        else:
            neither += 1

    print(f"📧 Email Only: {email_only} ({email_only / active_recipients * 100:.1f}%)")
    print(
        f"☁️  Upload Only: {upload_only} ({upload_only / active_recipients * 100:.1f}%)"
    )
    print(f"📧☁️  Both: {both} ({both / active_recipients * 100:.1f}%)")
    print(f"❌ Neither: {neither} ({neither / active_recipients * 100:.1f}%)")
    print("-" * 100)

    # Recipients without any preferences
    if without_prefs > 0:
        print(
            f"\n⚠️  WARNING: {without_prefs} recipients have NO preferences configured"
        )
        print("These recipients will NOT receive any publications:")
        print()

        for recipient in recipients:
            if not recipient.get("publication_preferences"):
                email = recipient["email"]
                status = "ACTIVE" if recipient.get("active", True) else "INACTIVE"
                print(f"  - {email} ({status})")

    print("\n" + "=" * 100)
    await service.close()


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage recipient publication preferences",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Add preference
    add_parser = subparsers.add_parser("add", help="Add preference to recipient")
    add_parser.add_argument("email", help="Recipient email address")
    add_parser.add_argument("publication_id", help="Publication ID")
    add_parser.add_argument(
        "--no-email", action="store_true", help="Disable email delivery"
    )
    add_parser.add_argument(
        "--no-upload", action="store_true", help="Disable OneDrive upload"
    )

    # Remove preference
    remove_parser = subparsers.add_parser(
        "remove", help="Remove preference from recipient"
    )
    remove_parser.add_argument("email", help="Recipient email address")
    remove_parser.add_argument("publication_id", help="Publication ID")

    # List preferences
    list_parser = subparsers.add_parser("list", help="List preferences for recipient")
    list_parser.add_argument("email", help="Recipient email address")

    # Bulk add
    bulk_add_parser = subparsers.add_parser(
        "bulk-add", help="Add preference to ALL recipients"
    )
    bulk_add_parser.add_argument("publication_id", help="Publication ID")
    bulk_add_parser.add_argument(
        "--no-email", action="store_true", help="Disable email delivery"
    )
    bulk_add_parser.add_argument(
        "--no-upload", action="store_true", help="Disable OneDrive upload"
    )

    # Bulk remove
    bulk_remove_parser = subparsers.add_parser(
        "bulk-remove", help="Remove preference from ALL recipients"
    )
    bulk_remove_parser.add_argument("publication_id", help="Publication ID")

    # Show statistics
    subparsers.add_parser("stats", help="Show preference statistics")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Execute command
    if args.command == "add":
        await add_preference(
            args.email,
            args.publication_id,
            email_enabled=not args.no_email,
            upload_enabled=not args.no_upload,
        )
    elif args.command == "remove":
        await remove_preference(args.email, args.publication_id)
    elif args.command == "list":
        await list_preferences(args.email)
    elif args.command == "bulk-add":
        await bulk_add_preference(
            args.publication_id,
            email_enabled=not args.no_email,
            upload_enabled=not args.no_upload,
        )
    elif args.command == "bulk-remove":
        await bulk_remove_preference(args.publication_id)
    elif args.command == "stats":
        await show_statistics()


if __name__ == "__main__":
    asyncio.run(main())
