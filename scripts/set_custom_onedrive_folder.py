"""
Set custom OneDrive folder for a specific recipient and publication.

This script updates the publication_preferences for a recipient to set a
custom_onedrive_folder for a specific publication.

Usage:
    python scripts/set_custom_onedrive_folder.py \
        --email "user@example.com" \
        --publication "megatrend-folger" \
        --folder "/Custom/Path"

    python scripts/set_custom_onedrive_folder.py \
        --email "user@example.com" \
        --publication "megatrend-folger" \
        --folder "/Custom/Path" \
        --dry-run  # Preview changes
"""

import argparse
import asyncio
import sys
from pathlib import Path

from depotbutler.db.mongodb import MongoDBService
from depotbutler.utils.logger import get_logger

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logger = get_logger(__name__)


async def set_custom_folder(
    email: str, publication_id: str, folder: str, dry_run: bool = True
) -> int:
    """
    Set custom OneDrive folder for a specific recipient and publication.

    Args:
        email: Recipient email address
        publication_id: Publication ID (e.g., "megatrend-folger")
        folder: Custom OneDrive folder path (e.g., "/Finance/2025")
        dry_run: If True, only show what would be done without making changes

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    logger.info("🔍 Setting custom OneDrive folder...")
    logger.info(f"   Email: {email}")
    logger.info(f"   Publication: {publication_id}")
    logger.info(f"   Folder: {folder}")

    if dry_run:
        logger.warning("\n⚠️  DRY RUN MODE - No changes will be made")

    async with MongoDBService() as db:
        # Step 1: Find the recipient
        logger.info("\n[Step 1/3] Finding recipient...")
        recipient = await db.db.recipients.find_one({"email": email})

        if not recipient:
            logger.error(f"❌ Recipient not found: {email}")
            return 1

        logger.info(f"✓ Found recipient: {recipient['email']}")

        # Step 2: Check if publication preference exists
        logger.info("\n[Step 2/3] Checking publication preferences...")
        publication_preferences = recipient.get("publication_preferences", [])

        if not publication_preferences:
            logger.error(
                "❌ Recipient has no publication preferences. "
                "Run add_recipient_preferences.py first."
            )
            return 1

        # Find the preference for this publication
        pref_index = None
        for i, pref in enumerate(publication_preferences):
            if pref.get("publication_id") == publication_id:
                pref_index = i
                break

        if pref_index is None:
            logger.error(
                f"❌ Recipient has no preference for publication: {publication_id}"
            )
            logger.info("\nAvailable publications in preferences:")
            for pref in publication_preferences:
                logger.info(f"  - {pref.get('publication_id')}")
            return 1

        current_folder = publication_preferences[pref_index].get(
            "custom_onedrive_folder"
        )
        logger.info(f"✓ Found preference for: {publication_id}")
        logger.info(f"  Current custom folder: {current_folder or '(not set)'}")
        logger.info(f"  New custom folder: {folder}")

        # Step 3: Update the preference
        if not dry_run:
            logger.info("\n[Step 3/3] Updating custom folder...")

            result = await db.db.recipients.update_one(
                {
                    "email": email,
                    "publication_preferences.publication_id": publication_id,
                },
                {"$set": {"publication_preferences.$.custom_onedrive_folder": folder}},
            )

            if result.modified_count > 0:
                logger.info("✅ Successfully updated custom folder!")
                logger.info(f"   {email}")
                logger.info(f"   Publication: {publication_id}")
                logger.info(f"   Folder: {folder}")
            else:
                logger.warning(
                    "⚠️  No changes made (folder may already be set to this value)"
                )

        else:
            logger.info("\n[Step 3/3] DRY RUN - Would execute this update:")
            logger.info("─" * 60)
            logger.info(f"  Recipient: {email}")
            logger.info(f"  Publication: {publication_id}")
            logger.info(f"  Set custom_onedrive_folder: {folder}")
            logger.info("─" * 60)
            logger.info("\nRun without --dry-run to apply changes")

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Set custom OneDrive folder for a recipient and publication"
    )
    parser.add_argument("--email", required=True, help="Recipient email address")
    parser.add_argument(
        "--publication",
        required=True,
        help="Publication ID (e.g., megatrend-folger)",
    )
    parser.add_argument(
        "--folder", required=True, help="Custom OneDrive folder path (e.g., /Finance)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them",
    )

    args = parser.parse_args()

    exit_code = asyncio.run(
        set_custom_folder(args.email, args.publication, args.folder, args.dry_run)
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
