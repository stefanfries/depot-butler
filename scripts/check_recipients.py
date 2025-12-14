"""
Enhanced recipient statistics and preferences viewer.

Usage:
    python scripts/check_recipients.py              # Show all recipients with preferences
    python scripts/check_recipients.py --simple     # Show basic statistics only
    python scripts/check_recipients.py --active     # Show only active recipients
    python scripts/check_recipients.py --inactive   # Show only inactive recipients
"""

import argparse
import asyncio
import sys
from pathlib import Path

from depotbutler.db.mongodb import get_mongodb_service

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


async def check_recipients(mode: str = "full", filter_active: bool | None = None):
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

    recipients = await service.db.recipients.find(query).sort("email", 1).to_list(None)

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
    print(f"📊 RECIPIENT OVERVIEW")
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
                print(f"   ⚠️  No preferences configured (will receive nothing)")

            print()

    print("=" * 100)
    await service.close()


async def main():
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

    args = parser.parse_args()

    # Determine mode and filter
    mode = "simple" if args.simple else "full"
    filter_active = None
    if args.active:
        filter_active = True
    elif args.inactive:
        filter_active = False

    await check_recipients(mode=mode, filter_active=filter_active)


if __name__ == "__main__":
    asyncio.run(main())
