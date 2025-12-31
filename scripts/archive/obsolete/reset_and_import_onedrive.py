"""
Reset MongoDB and Import from OneDrive (Primary Source)

This script:
1. Backs up current MongoDB data (if any)
2. Clears all web_historical editions (incorrect date-based keys)
3. Runs OneDrive import as PRIMARY data source
4. Reports completeness statistics

Usage:
    # Dry-run (preview only)
    uv run python scripts/reset_and_import_onedrive.py --dry-run

    # Execute (clears MongoDB and imports)
    uv run python scripts/reset_and_import_onedrive.py

Context:
    - Website dates are unreliable (don't match PDF headers)
    - OneDrive filenames contain correct dates from PDF headers
    - New edition_key format: {issue}_{year}_{publication_id} (issue-based)
    - Example: 18_2019_megatrend-folger (instead of 2019-04-25_megatrend-folger)
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from depotbutler.db.mongodb import get_mongodb_service
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


async def backup_mongodb_data() -> Path | None:
    """
    Create backup of current MongoDB data.

    Returns:
        Path to backup file, or None if no data to backup
    """
    logger.info("=" * 70)
    logger.info("STEP 1: Backing up current MongoDB data")
    logger.info("=" * 70)

    mongodb = await get_mongodb_service()

    # Query all editions
    all_editions = await mongodb.db["processed_editions"].find().to_list(None)

    if not all_editions:
        logger.info("No editions found in MongoDB, skipping backup")
        return None

    # Create backup file
    backup_dir = Path("data/tmp/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"mongodb_backup_{timestamp}.json"

    # Convert ObjectId to string for JSON serialization
    backup_data = []
    for edition in all_editions:
        edition["_id"] = str(edition["_id"])
        backup_data.append(edition)

    # Write backup
    backup_file.write_text(json.dumps(backup_data, indent=2, default=str))

    logger.info(f"✓ Backed up {len(backup_data)} editions to:")
    logger.info(f"  {backup_file}")
    logger.info("")

    return backup_file


async def clear_mongodb(dry_run: bool = False) -> int:
    """
    Clear all editions from MongoDB.

    Args:
        dry_run: If True, only preview without actual deletion

    Returns:
        Number of editions that would be/were deleted
    """
    logger.info("=" * 70)
    logger.info("STEP 2: Clearing MongoDB")
    logger.info("=" * 70)

    mongodb = await get_mongodb_service()

    # Count editions
    count = await mongodb.db["processed_editions"].count_documents({})

    if count == 0:
        logger.info("MongoDB is already empty, nothing to clear")
        logger.info("")
        return 0

    logger.info(f"Found {count} editions in MongoDB")

    if dry_run:
        logger.info("[DRY-RUN] Would delete all editions")
    else:
        result = await mongodb.db["processed_editions"].delete_many({})
        logger.info(f"✓ Deleted {result.deleted_count} editions")

    logger.info("")
    return count


async def run_onedrive_import(dry_run: bool = False) -> None:
    """
    Run OneDrive import script.

    Args:
        dry_run: If True, preview only without actual uploads
    """
    logger.info("=" * 70)
    logger.info("STEP 3: Running OneDrive Import (Primary Source)")
    logger.info("=" * 70)

    # Import the script module
    import import_from_onedrive

    # Run the import
    await import_from_onedrive.run_import(
        start_year=None,  # Import all years
        end_year=None,
        dry_run=dry_run,
    )


async def analyze_completeness() -> None:
    """
    Analyze completeness of imported data.
    """
    logger.info("=" * 70)
    logger.info("STEP 4: Analyzing Completeness")
    logger.info("=" * 70)

    mongodb = await get_mongodb_service()

    # Query all editions, grouped by year
    all_editions = (
        await mongodb.db["processed_editions"]
        .find()
        .sort("publication_date", 1)
        .to_list(None)
    )

    if not all_editions:
        logger.info("No editions found in MongoDB")
        return

    # Group by year
    import re
    from collections import defaultdict

    editions_by_year = defaultdict(list)

    for edition in all_editions:
        title = edition["title"]
        # Extract year from title like "Megatrend Folger 18/2019"
        match = re.search(r"(\d+)/(\d{4})", title)
        if match:
            year = match.group(2)
            issue = int(match.group(1))
            editions_by_year[year].append(issue)

    # Report statistics
    logger.info(f"Total editions: {len(all_editions)}")
    logger.info("")
    logger.info("Editions by year:")

    total_years = 0
    total_issues = 0

    for year in sorted(editions_by_year.keys()):
        issues = sorted(set(editions_by_year[year]))
        count = len(issues)
        total_years += 1
        total_issues += count

        # Check for gaps
        expected = set(range(1, 53))  # Issues 1-52
        missing = sorted(expected - set(issues))

        missing_str = ""
        if missing:
            if len(missing) <= 10:
                missing_str = f" (Missing: {', '.join(map(str, missing))})"
            else:
                missing_str = f" (Missing {len(missing)} issues)"

        logger.info(f"  {year}: {count} issues{missing_str}")

    logger.info("")
    logger.info("Summary:")
    logger.info(f"  Years covered: {total_years}")
    logger.info(f"  Total issues: {total_issues}")
    logger.info(f"  Average per year: {total_issues / total_years:.1f}")
    logger.info("")


async def main() -> None:
    """Main entry point."""
    # Check for flags
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        logger.info("🔍 DRY-RUN MODE: No actual changes will be made")
        logger.info("")

    try:
        # Step 1: Backup
        await backup_mongodb_data()

        # Step 2: Clear MongoDB
        await clear_mongodb(dry_run)

        # Step 3: Import from OneDrive
        await run_onedrive_import(dry_run)

        # Step 4: Analyze completeness
        if not dry_run:
            await analyze_completeness()

        logger.info("=" * 70)
        logger.info("✓ RESET AND IMPORT COMPLETE")
        logger.info("=" * 70)

        if dry_run:
            logger.info("")
            logger.info("To execute for real, run:")
            logger.info("  uv run python scripts/reset_and_import_onedrive.py")

    except Exception as e:
        logger.error(f"❌ Error during reset and import: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
