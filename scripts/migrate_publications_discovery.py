"""
Migration script to add discovery fields to publications collection.

This script:
1. Adds discovered, last_seen, first_discovered fields to existing publications
2. Sets discovered=true for existing publications (they were manually configured)
3. Supports dry-run mode to preview changes
"""

import asyncio
import sys
from datetime import datetime, timezone

from depotbutler.db.mongodb import get_mongodb_service
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


async def migrate_publications_discovery(dry_run: bool = False):
    """
    Add discovery fields to all publications.

    Args:
        dry_run: If True, only preview changes without applying them
    """
    logger.info("=" * 80)
    logger.info("Starting publications discovery fields migration")
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    logger.info("=" * 80)

    try:
        # Connect to MongoDB
        mongodb = await get_mongodb_service()

        # Step 1: Count publications without discovery fields
        logger.info("\n[Step 1/2] Checking publications...")
        total_publications = await mongodb.db.publications.count_documents({})
        publications_without_discovery = await mongodb.db.publications.count_documents(
            {"discovered": {"$exists": False}}
        )

        logger.info(f"Total publications: {total_publications}")
        logger.info(
            f"Publications without discovery fields: {publications_without_discovery}"
        )

        if publications_without_discovery == 0:
            logger.info("✓ All publications already have discovery fields")
            logger.info("No migration needed")
            return True

        # Step 2: Add discovery fields
        logger.info(
            f"\n[Step 2/2] Adding discovery fields to {publications_without_discovery} publications..."
        )

        now = datetime.now(timezone.utc)

        if not dry_run:
            # Get publications that need migration
            publications = await mongodb.db.publications.find(
                {"discovered": {"$exists": False}}
            ).to_list(None)

            updated_count = 0
            for pub in publications:
                # Existing publications are marked as discovered (they were manually configured)
                # first_discovered = when they were created, or now if not available
                first_discovered = pub.get("created_at", now)

                result = await mongodb.db.publications.update_one(
                    {"_id": pub["_id"]},
                    {
                        "$set": {
                            "discovered": True,
                            "last_seen": now,
                            "first_discovered": first_discovered,
                            "updated_at": now,
                        }
                    },
                )

                if result.modified_count > 0:
                    updated_count += 1
                    logger.info(
                        f"  ✓ Migrated: {pub.get('name', pub.get('publication_id'))}"
                    )

            logger.info(f"\n✓ Updated {updated_count} publications")

            if updated_count != publications_without_discovery:
                logger.warning(
                    f"Expected to update {publications_without_discovery} but updated {updated_count}"
                )
        else:
            # Dry run - show what would be migrated
            publications = await mongodb.db.publications.find(
                {"discovered": {"$exists": False}}
            ).to_list(None)

            logger.info("[DRY RUN] Would migrate the following publications:")
            for pub in publications:
                logger.info(
                    f"  - {pub.get('name', pub.get('publication_id'))} (ID: {pub.get('publication_id')})"
                )

        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("Migration Summary")
        logger.info("=" * 80)
        logger.info(f"Total publications: {total_publications}")
        logger.info(f"Publications migrated: {publications_without_discovery}")
        logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
        logger.info("=" * 80)

        if dry_run:
            logger.info("\n✓ Dry run completed successfully")
            logger.info("Run without --dry-run to apply changes")
        else:
            logger.info("\n✓ Migration completed successfully")
            logger.info(
                "\nNote: Existing publications marked as 'discovered=true'"
            )
            logger.info(
                "      because they were manually configured before auto-discovery."
            )

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
        description="Migrate publications collection to add discovery fields"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them",
    )

    args = parser.parse_args()

    try:
        result = asyncio.run(migrate_publications_discovery(dry_run=args.dry_run))
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        logger.info("\nMigration cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
