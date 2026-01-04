"""
Enhanced recipient statistics and preferences viewer.

Usage:
    uv run python scripts/check_recipients.py              # Show all recipients with preferences
    uv run python scripts/check_recipients.py --simple     # Show basic statistics only
    uv run python scripts/check_recipients.py --active     # Show only active recipients
    uv run python scripts/check_recipients.py --inactive   # Show only inactive recipients
    uv run python scripts/check_recipients.py --stats      # Show detailed preference statistics
    uv run python scripts/check_recipients.py --coverage   # Show per-publication coverage
"""

import argparse
import asyncio
import sys
from pathlib import Path

from depotbutler.db.mongodb import get_mongodb_service

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


async def check_recipients(
    mode: str = "full", filter_active: bool | None = None
) -> None:
    """
    Display recipient information with various detail levels.

    Args:
        mode: "full" (with preferences), "simple" (basic stats only)
        filter_active: None (all), True (active only), False (inactive only)
    """
    service = await get_mongodb_service()

    # Build query filter
    query = {}
    if filter_active is not None:
        query["active"] = filter_active

    recipients = await service.db.recipients.find(query).sort("email", 1).to_list(None)  # type: ignore

    if not recipients:
        print("\n❌ No recipients found")
        await service.close()
        return

    # Get publications for display
    publications = await service.get_publications(active_only=False)
    pub_map = {p["publication_id"]: p["name"] for p in publications}

    # Summary statistics
    total = len(recipients)
    active = sum(1 for r in recipients if r.get("active", True))
    with_prefs = sum(1 for r in recipients if r.get("publication_preferences"))

    print("\n" + "=" * 100)
    print("📊 RECIPIENT OVERVIEW")
    print("=" * 100)
    print(f"Total Recipients: {total}")
    print(f"Active: {active} | Inactive: {total - active}")
    print(f"With Preferences: {with_prefs} | Without: {total - with_prefs}")
    print("=" * 100)

    if mode == "simple":
        # Simple mode: just basic stats
        print(f"\n{'Email':<40} | {'Name':<20} | Status | {'Count':>5} | Last Sent")
        print("-" * 100)

        for r in recipients:
            email = r["email"]
            name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip()
            status = "✓" if r.get("active", True) else "✗"
            count = r.get("send_count", 0)
            last_sent = (
                str(r["last_sent_at"])[:19] if r.get("last_sent_at") else "Never"
            )

            print(f"{email:<40} | {name:<20} | {status:^6} | {count:>5} | {last_sent}")

    else:
        # Full mode: show preferences
        print()
        for idx, r in enumerate(recipients, 1):
            email = r["email"]
            name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip()
            status = "✓ ACTIVE" if r.get("active", True) else "✗ INACTIVE"
            count = r.get("send_count", 0)
            last_sent = (
                str(r["last_sent_at"])[:19] if r.get("last_sent_at") else "Never"
            )

            print(f"{idx}. {email}")
            print(f"   Name: {name}")
            print(f"   Status: {status}")
            print(f"   Deliveries: {count} | Last: {last_sent}")

            # Show preferences
            prefs = r.get("publication_preferences", [])
            if prefs:
                print(f"   Publications ({len(prefs)}):")
                for pref in prefs:
                    pub_id = pref.get("publication_id", "unknown")
                    pub_name = pub_map.get(pub_id, pub_id)
                    enabled = "✓" if pref.get("enabled", True) else "✗"
                    email_icon = "📧" if pref.get("email_enabled", True) else "  "
                    upload_icon = "☁️" if pref.get("upload_enabled", True) else "  "

                    print(
                        f"      {enabled} {pub_name} | {email_icon} Email | {upload_icon} Upload"
                    )
            else:
                print("   ⚠️  No preferences configured (will receive nothing)")

            print()

    print("=" * 100)
    await service.close()


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="View recipient statistics and preferences"
    )
    parser.add_argument(
        "--simple", action="store_true", help="Show basic statistics only"
    )
    parser.add_argument(
        "--active", action="store_true", help="Show only active recipients"
    )
    parser.add_argument(
        "--inactive", action="store_true", help="Show only inactive recipients"
    )
    parser.add_argument(
        "--stats", action="store_true", help="Show detailed preference statistics"
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Show per-publication coverage statistics",
    )

    args = parser.parse_args()

    # Handle stats mode
    if args.stats or args.coverage:
        await show_preference_statistics(coverage_only=args.coverage)
        return

    # Determine mode and filter
    mode = "simple" if args.simple else "full"
    filter_active = None
    if args.active:
        filter_active = True
    elif args.inactive:
        filter_active = False

    await check_recipients(mode=mode, filter_active=filter_active)


async def show_preference_statistics(coverage_only: bool = False) -> None:
    """Show detailed preference statistics across all recipients."""
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

    if not coverage_only:
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

    if coverage_only:
        await service.close()
        return

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


if __name__ == "__main__":
    asyncio.run(main())
