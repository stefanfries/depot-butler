"""
Add default publication preferences to all recipients.

This script adds explicit publication preferences to recipients who:
- Have no publication_preferences field
- Have an empty publication_preferences array

After the opt-in model change, recipients without preferences will receive nothing.
This script ensures all existing recipients are configured to receive all active publications.

Usage:
    python scripts/add_recipient_preferences.py --dry-run  # Preview changes
    python scripts/add_recipient_preferences.py            # Apply changes
"""

import argparse
import asyncio
import sys
from pathlib import Path

from depotbutler.db.mongodb import MongoDBService, get_publications
from depotbutler.utils.logger import get_logger

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logger = get_logger(__name__)


async def add_default_preferences(dry_run: bool = True):
    """
    Add default publication preferences to all recipients without them.

    Args:
        dry_run: If True, only show what would be done without making changes
    """
    logger.info("🔍 Starting recipient preferences migration...")

    if dry_run:
        logger.warning("DRY RUN MODE - No changes will be made")

    async with MongoDBService() as db:
        # Step 1: Get all active publications
        logger.info("\n[Step 1/4] Fetching active publications...")
        publications = await get_publications(active_only=True)

        if not publications:
            logger.error("❌ No active publications found in database")
            return 1

        logger.info(f"Found {len(publications)} active publication(s):")
        for pub in publications:
            logger.info(f"  - {pub['publication_id']}: {pub['name']}")

        # Step 2: Build default preferences array
        logger.info("\n[Step 2/4] Building default preferences...")
        default_prefs = []
        for pub in publications:
            pref = {
                "publication_id": pub["publication_id"],
                "enabled": True,
                "email_enabled": pub.get("email_enabled", True),
                "upload_enabled": pub.get("onedrive_enabled", True),
                "send_count": 0,
                "last_sent_at": None,
            }
            default_prefs.append(pref)
            logger.info(
                f"  ✓ {pub['publication_id']}: "
                f"email={pref['email_enabled']}, "
                f"upload={pref['upload_enabled']}"
            )

        # Step 3: Find recipients without preferences (both active and inactive)
        logger.info("\n[Step 3/4] Finding recipients without preferences...")
        query = {
            "$or": [
                {"publication_preferences": {"$exists": False}},
                {"publication_preferences": {"$size": 0}},
            ],
        }

        recipients_cursor = db.db.recipients.find(query).sort("email", 1)  # type: ignore
        recipients = await recipients_cursor.to_list(length=None)

        if not recipients:
            logger.info("✅ All recipients already have publication preferences!")
            return 0

        logger.warning(
            f"\n⚠️  Found {len(recipients)} recipient(s) without preferences:"
        )
        for recipient in recipients:
            current_prefs = recipient.get("publication_preferences", [])
            status = "empty array" if current_prefs == [] else "missing field"
            active_status = "active" if recipient.get("active", True) else "inactive"
            logger.warning(f"  - {recipient['email']} ({status}, {active_status})")

        # Step 4: Confirm and update
        if not dry_run:
            logger.warning(
                f"\n[Step 4/4] This will add preferences for {len(publications)} "
                f"publication(s) to {len(recipients)} recipient(s)"
            )
            response = input("\nProceed with update? (yes/no): ").strip().lower()

            if response != "yes":
                logger.info("❌ Update cancelled by user")
                return 0

            logger.info("\n🔄 Updating recipients...")
            updated_count = 0
            failed_count = 0

            for recipient in recipients:
                try:
                    result = await db.db.recipients.update_one(
                        {"_id": recipient["_id"]},
                        {"$set": {"publication_preferences": default_prefs}},
                    )

                    if result.modified_count > 0:
                        updated_count += 1
                        logger.info(f"  ✓ Updated: {recipient['email']}")
                    else:
                        logger.warning(f"  ⚠️  No change: {recipient['email']}")

                except Exception as e:
                    failed_count += 1
                    logger.error(f"  ✗ Failed: {recipient['email']} - {e}")

            logger.info(f"\n{'='*60}")
            logger.info(
                f"✅ Migration complete: "
                f"{updated_count} updated, {failed_count} failed"
            )
            logger.info(f"{'='*60}")

            if failed_count > 0:
                return 1

        else:
            logger.info(
                f"\n[Step 4/4] DRY RUN - Would update {len(recipients)} recipient(s)"
            )
            logger.info("\nExample of what would be added:")
            logger.info("─" * 60)
            for pref in default_prefs:
                logger.info(f"  • {pref['publication_id']}:")
                logger.info(f"      enabled: {pref['enabled']}")
                logger.info(f"      email_enabled: {pref['email_enabled']}")
                logger.info(f"      upload_enabled: {pref['upload_enabled']}")
            logger.info("─" * 60)
            logger.info(
                "\n💡 Run without --dry-run to apply changes:\n"
                "   python scripts/add_recipient_preferences.py"
            )

        return 0


async def main():
    """Parse arguments and run migration."""
    parser = argparse.ArgumentParser(
        description="Add default publication preferences to all recipients"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying database",
    )

    args = parser.parse_args()

    try:
        return await add_default_preferences(dry_run=args.dry_run)
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
