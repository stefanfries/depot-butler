"""
Migrate all existing edition metadata to standardize metadata fields.

All current entries in the database came from scheduled jobs, which use
temporary files. This script:
1. Sets file_path to empty string (temp files not persisted)
2. Sets source to "scheduled_job" (tracking ingestion method)

Usage:
    uv run python scripts/migrate_file_paths.py --dry-run  # Preview changes
    uv run python scripts/migrate_file_paths.py            # Apply changes
"""

import argparse
import asyncio

from depotbutler.db.mongodb import MongoDBService
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


async def migrate_file_paths(dry_run: bool = False) -> None:
    """
    Update all editions to standardize metadata fields.

    Sets:
    - file_path to empty string (scheduled jobs use temp files)
    - source to "scheduled_job" (track ingestion method)

    Args:
        dry_run: If True, only preview changes without applying them
    """
    async with MongoDBService() as db:
        # Get all editions
        assert db.edition_repo is not None
        cursor = db.edition_repo.collection.find({})
        all_editions = await cursor.to_list(length=None)

        logger.info("Found %d total editions in database", len(all_editions))

        # Filter editions that need updating
        editions_needing_file_path_update = [
            ed for ed in all_editions if ed.get("file_path", "") != ""
        ]
        editions_needing_source_update = [
            ed for ed in all_editions if "source" not in ed
        ]

        logger.info(
            "%d editions have non-empty file_path",
            len(editions_needing_file_path_update),
        )
        logger.info(
            "%d editions are missing source field", len(editions_needing_source_update)
        )

        # Determine which editions need any update
        edition_keys_to_update = set()
        for ed in editions_needing_file_path_update:
            edition_keys_to_update.add(ed.get("edition_key"))
        for ed in editions_needing_source_update:
            edition_keys_to_update.add(ed.get("edition_key"))

        logger.info("%d unique editions need updating", len(edition_keys_to_update))

        if not edition_keys_to_update:
            logger.info("✅ No editions need updating - database is already clean")
            return

        # Show sample of what will be changed
        logger.info("\n📋 Sample of editions to update:")
        sample_editions = [
            ed for ed in all_editions if ed.get("edition_key") in edition_keys_to_update
        ][:5]

        for edition in sample_editions:
            key = edition.get("edition_key", "unknown")
            current_file_path = edition.get("file_path", "")
            has_source = "source" in edition

            changes = []
            if current_file_path != "":
                changes.append(f"file_path: '{current_file_path}' → ''")
            if not has_source:
                changes.append("source: (missing) → 'scheduled_job'")

            logger.info("  • %s:", key)
            for change in changes:
                logger.info("      - %s", change)

        if len(edition_keys_to_update) > 5:
            logger.info("  ... and %d more", len(edition_keys_to_update) - 5)

        if dry_run:
            logger.info(
                "\n🔍 DRY RUN MODE - No changes applied. Run without --dry-run to apply changes."
            )
            return

        # Apply updates
        logger.info("\n🔄 Updating edition metadata...")

        # Update in a single operation using $or to match either condition
        result = await db.edition_repo.collection.update_many(
            {
                "$or": [
                    {"file_path": {"$ne": ""}},  # Has non-empty file_path
                    {"source": {"$exists": False}},  # Missing source field
                ]
            },
            {"$set": {"file_path": "", "source": "scheduled_job"}},
        )

        logger.info(
            "✅ Migration complete: Updated %d editions (matched: %d)",
            result.modified_count,
            result.matched_count,
        )

        # Verify the changes
        remaining_file_paths = await db.edition_repo.collection.count_documents(
            {"file_path": {"$ne": ""}}
        )
        missing_source = await db.edition_repo.collection.count_documents(
            {"source": {"$exists": False}}
        )

        if remaining_file_paths == 0 and missing_source == 0:
            logger.info(
                "✅ Verification passed: All file_paths are empty and all editions have source field"
            )
        else:
            if remaining_file_paths > 0:
                logger.warning(
                    "⚠️  Warning: %d editions still have non-empty file_path",
                    remaining_file_paths,
                )
            if missing_source > 0:
                logger.warning(
                    "⚠️  Warning: %d editions still missing source field",
                    missing_source,
                )


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate edition metadata: set file_path to empty and add source field"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them",
    )
    args = parser.parse_args()

    asyncio.run(migrate_file_paths(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
