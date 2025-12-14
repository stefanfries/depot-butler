"""
Migration script to add publication_preferences field to recipients collection.

This script:
1. Adds empty publication_preferences array to all recipients
2. Creates MongoDB index on publication_preferences.publication_id
3. Supports dry-run mode to preview changes
"""

import asyncio
import sys
from datetime import datetime, timezone

from depotbutler.db.mongodb import get_mongodb_service
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


async def migrate_recipient_preferences(dry_run: bool = False):
    """
    Add publication_preferences field to all recipients.

    Args:
        dry_run: If True, only preview changes without applying them
    """
    logger.info("=" * 80)
    logger.info("Starting recipient preferences migration")
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    logger.info("=" * 80)

    try:
        # Connect to MongoDB
        mongodb = await get_mongodb_service()

        # Step 1: Count recipients without publication_preferences
        logger.info("\n[Step 1/3] Checking recipients...")
        total_recipients = await mongodb.db.recipients.count_documents({})
        recipients_without_prefs = await mongodb.db.recipients.count_documents({
            "publication_preferences": {"$exists": False}
        })

        logger.info(f"Total recipients: {total_recipients}")
        logger.info(
            f"Recipients without preferences: {recipients_without_prefs}"
        )

        if recipients_without_prefs == 0:
            logger.info("✓ All recipients already have publication_preferences field")
            logger.info("No migration needed")
            return True

        # Step 2: Add publication_preferences field
        logger.info(
            f"\n[Step 2/3] Adding publication_preferences to {recipients_without_prefs} recipients..."
        )

        if not dry_run:
            result = await mongodb.db.recipients.update_many(
                {"publication_preferences": {"$exists": False}},
                {
                    "$set": {
                        "publication_preferences": [],
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )

            logger.info(f"✓ Updated {result.modified_count} recipients")

            if result.modified_count != recipients_without_prefs:
                logger.warning(
                    f"Expected to update {recipients_without_prefs} but updated {result.modified_count}"
                )
        else:
            logger.info(
                f"[DRY RUN] Would update {recipients_without_prefs} recipients"
            )

        # Step 3: Create index on publication_preferences.publication_id
        logger.info(
            "\n[Step 3/3] Creating index on publication_preferences.publication_id..."
        )

        if not dry_run:
            # Check if index already exists
            existing_indexes = await mongodb.db.recipients.index_information()
            index_name = "publication_preferences.publication_id_1"

            if index_name in existing_indexes:
                logger.info(f"✓ Index '{index_name}' already exists")
            else:
                await mongodb.db.recipients.create_index(
                    [("publication_preferences.publication_id", 1)]
                )
                logger.info(f"✓ Created index '{index_name}'")
        else:
            logger.info("[DRY RUN] Would create index on publication_preferences.publication_id")

        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("Migration Summary")
        logger.info("=" * 80)
        logger.info(f"Total recipients: {total_recipients}")
        logger.info(f"Recipients migrated: {recipients_without_prefs}")
        logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
        logger.info("=" * 80)

        if dry_run:
            logger.info("\n✓ Dry run completed successfully")
            logger.info("Run without --dry-run to apply changes")
        else:
            logger.info("\n✓ Migration completed successfully")

        return True

    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        return False
    finally:
        await mongodb.close()


def main():
    """Run the migration script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate recipients collection to add publication_preferences"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them",
    )

    args = parser.parse_args()

    try:
        result = asyncio.run(migrate_recipient_preferences(dry_run=args.dry_run))
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        logger.info("\nMigration cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
