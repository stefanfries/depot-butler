"""
OneDrive PDF Import Script

Imports historical PDFs from local OneDrive folder to Azure Blob Storage and MongoDB.
Parses standardized filenames to extract metadata and performs deduplication.

Filename Format: YYYY-MM-DD_Edition-Name_II-YYYY.pdf
Example: 2014-03-06_Die-800%-Strategie_01-2014.pdf

Usage:
    # Dry-run (scan and preview, no uploads)
    uv run python scripts/import_from_onedrive.py --dry-run

    # Import specific year range
    uv run python scripts/import_from_onedrive.py --start-year 2014 --end-year 2017

    # Import all available files
    uv run python scripts/import_from_onedrive.py

Features:
    - Parses standardized filenames for metadata extraction
    - Checks MongoDB for duplicates before uploading
    - Archives PDFs to Azure Blob Storage
    - Updates MongoDB with source="onedrive_import"
    - Progress reporting and statistics
    - Dry-run mode for safe testing
    - Year range filtering

Requirements:
    - Azure Storage connection configured
    - MongoDB connection configured
    - OneDrive folder synced locally
    - All filenames standardized (run rename_onedrive_pdfs.py first)
"""

from __future__ import annotations

import argparse
import asyncio

# Configure file logging to avoid Windows console encoding issues with emojis
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple

from depotbutler.db.mongodb import MongoDBService, get_mongodb_service
from depotbutler.services.blob_storage_service import BlobStorageService
from depotbutler.utils.logger import get_logger

log_file = Path("data/tmp/onedrive_import.log")
log_file.parent.mkdir(parents=True, exist_ok=True)
file_handler = logging.FileHandler(log_file, encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)

logger = get_logger(__name__)
logger.addHandler(file_handler)

# OneDrive base path
ONEDRIVE_BASE = Path(
    r"C:\Users\stefa\OneDrive\Dokumente\Banken\DerAktionaer\Strategie_800-Prozent"
)

# Publication name to ID mapping (hardcoded, only 2 publications)
PUBLICATION_MAP = {
    "Die-800%-Strategie": "die-800-prozent-strategie",
    "Megatrend-Folger": "megatrend-folger",
}


class ParsedFilename(NamedTuple):
    """Parsed filename metadata."""

    date: str  # YYYY-MM-DD
    publication_name: str  # Die-800%-Strategie or Megatrend-Folger
    publication_id: str  # die-800-prozent-strategie or megatrend-folger
    issue: str  # II (2-digit)
    year: str  # YYYY (4-digit)


class ImportStats(NamedTuple):
    """Import operation statistics."""

    total_files: int
    already_exists: int
    uploaded: int
    errors: int
    skipped: int


def parse_standardized_filename(filename: str) -> ParsedFilename | None:
    """
    Parse standardized filename to extract metadata.

    Expected format: YYYY-MM-DD_Edition-Name_II-YYYY.pdf

    Args:
        filename: Standardized PDF filename

    Returns:
        ParsedFilename with metadata, or None if parsing fails
    """
    # Pattern: YYYY-MM-DD_Publication-Name_II-YYYY.pdf
    # Examples:
    #   2014-03-06_Die-800%-Strategie_01-2014.pdf
    #   2025-10-23_Megatrend-Folger_43-2025.pdf
    pattern = r"^(\d{4}-\d{2}-\d{2})_(Die-800%-Strategie|Megatrend-Folger)_(\d{2})-(\d{4})\.pdf$"

    match = re.match(pattern, filename)
    if not match:
        return None

    date_str = match.group(1)
    publication_name = match.group(2)
    issue = match.group(3)
    year = match.group(4)

    # Map publication name to ID
    publication_id = PUBLICATION_MAP.get(publication_name)
    if not publication_id:
        logger.error(f"Unknown publication name: {publication_name}")
        return None

    return ParsedFilename(
        date=date_str,
        publication_name=publication_name,
        publication_id=publication_id,
        issue=issue,
        year=year,
    )


def construct_edition_key(date: str, publication_id: str) -> str:
    """
    Construct edition key from date and publication ID.

    Args:
        date: Publication date (YYYY-MM-DD)
        publication_id: Publication identifier

    Returns:
        Edition key (e.g., "2014-03-06_die-800-prozent-strategie")
    """
    return f"{date}_{publication_id}"


async def collect_import_candidates(
    start_year: int | None = None,
    end_year: int | None = None,
) -> list[tuple[Path, ParsedFilename]]:
    """
    Scan OneDrive folder and collect files to import.

    Args:
        start_year: Optional start year filter (inclusive)
        end_year: Optional end year filter (inclusive)

    Returns:
        List of (file_path, parsed_metadata) tuples
    """
    candidates: list[tuple[Path, ParsedFilename]] = []

    # Scan year folders
    for year_folder in sorted(ONEDRIVE_BASE.iterdir()):
        if not year_folder.is_dir():
            continue

        year_name = year_folder.name
        if not (year_name.isdigit() and len(year_name) == 4):
            continue

        year_int = int(year_name)

        # Apply year filters
        if start_year and year_int < start_year:
            continue
        if end_year and year_int > end_year:
            continue

        logger.info(f"Scanning year folder: {year_name}")

        # Scan PDF files
        pdf_files = list(year_folder.glob("*.pdf"))
        logger.info(f"  Found {len(pdf_files)} PDF files")

        for pdf_path in sorted(pdf_files):
            parsed = parse_standardized_filename(pdf_path.name)
            if not parsed:
                logger.warning(f"  ⚠️  Failed to parse: {pdf_path.name}")
                continue

            candidates.append((pdf_path, parsed))

    logger.info(f"\n✓ Collected {len(candidates)} import candidates")
    return candidates


async def check_edition_exists(
    db: MongoDBService,
    edition_key: str,
) -> bool:
    """
    Check if edition already exists in MongoDB.

    Args:
        db: MongoDB service instance
        edition_key: Edition key to check

    Returns:
        True if edition exists, False otherwise
    """
    assert db.edition_repo is not None, "Edition repository not initialized"

    try:
        exists = await db.edition_repo.is_edition_processed(edition_key)
        return bool(exists)
    except Exception as e:
        logger.error(f"Error checking edition {edition_key}: {e}")
        return False


async def import_edition(
    db: MongoDBService,
    blob_service: BlobStorageService,
    pdf_path: Path,
    parsed: ParsedFilename,
    dry_run: bool = False,
) -> bool:
    """
    Import single edition to blob storage and MongoDB.

    Args:
        db: MongoDB service instance
        blob_service: Blob storage service instance
        pdf_path: Path to PDF file
        parsed: Parsed filename metadata
        dry_run: If True, skip actual upload and database write

    Returns:
        True if import successful, False otherwise
    """
    edition_key = construct_edition_key(parsed.date, parsed.publication_id)

    try:
        # Read PDF file
        pdf_bytes = pdf_path.read_bytes()
        file_size_bytes = len(pdf_bytes)
        file_size_mb = file_size_bytes / (1024 * 1024)

        logger.info(
            f"  📄 {parsed.publication_name} Issue {parsed.issue}/{parsed.year} "
            f"({file_size_mb:.2f} MB)"
        )

        if dry_run:
            logger.info("    [DRY-RUN] Would upload to blob storage and update MongoDB")
            return True

        # Upload to blob storage
        filename = pdf_path.name
        upload_result = await blob_service.archive_edition(
            pdf_bytes=pdf_bytes,
            publication_id=parsed.publication_id,
            date=parsed.date,
            filename=filename,
            metadata={
                "source": "onedrive_import",
                "publication_name": parsed.publication_name,
                "issue": parsed.issue,
                "year": parsed.year,
            },
        )

        blob_url = upload_result["blob_url"]
        blob_path = upload_result["blob_path"]

        logger.info(f"    ✓ Uploaded to: {blob_path}")

        # Create MongoDB entry
        assert db.edition_repo is not None, "Edition repository not initialized"

        success = await db.edition_repo.mark_edition_processed(
            edition_key=edition_key,
            title=f"{parsed.publication_name} {parsed.issue}/{parsed.year}",
            publication_date=parsed.date,
            download_url="",  # Not applicable for OneDrive imports
            file_path=f"OneDrive/{parsed.year}/{filename}",  # Permanent path reference
            blob_url=blob_url,
            blob_path=blob_path,
            blob_container=blob_service.container_name,
            file_size_bytes=file_size_bytes,
            archived_at=datetime.now(UTC),
            source="onedrive_import",
        )

        if success:
            logger.info(f"    ✓ MongoDB entry created: {edition_key}")
            return True
        else:
            logger.error(f"    ❌ Failed to create MongoDB entry: {edition_key}")
            return False

    except Exception as e:
        logger.error(f"    ❌ Import failed: {e}", exc_info=True)
        return False


async def run_import(
    start_year: int | None = None,
    end_year: int | None = None,
    dry_run: bool = False,
) -> ImportStats:
    """
    Run OneDrive import process.

    Args:
        start_year: Optional start year filter
        end_year: Optional end year filter
        dry_run: If True, preview only without actual uploads

    Returns:
        Import statistics
    """
    logger.info("=" * 80)
    logger.info("OneDrive PDF Import Script")
    logger.info("=" * 80)
    logger.info(f"Base folder: {ONEDRIVE_BASE}")

    if start_year or end_year:
        year_range = f"{start_year or 'all'} - {end_year or 'all'}"
        logger.info(f"Year filter: {year_range}")

    if dry_run:
        logger.info("🔍 DRY-RUN MODE: No uploads or database changes")

    logger.info("")

    # Initialize services
    db = await get_mongodb_service()
    blob_service = BlobStorageService()

    # Collect import candidates
    candidates = await collect_import_candidates(start_year, end_year)

    if not candidates:
        logger.info("No files to import")
        return ImportStats(0, 0, 0, 0, 0)

    # Process candidates
    total_files = len(candidates)
    already_exists = 0
    uploaded = 0
    errors = 0
    skipped = 0

    logger.info("\n" + "=" * 80)
    logger.info("Processing Import Candidates")
    logger.info("=" * 80)

    for idx, (pdf_path, parsed) in enumerate(candidates, 1):
        edition_key = construct_edition_key(parsed.date, parsed.publication_id)

        logger.info(
            f"\n[{idx}/{total_files}] {parsed.date} - {parsed.publication_name} "
            f"Issue {parsed.issue}/{parsed.year}"
        )

        # Check if edition already exists
        exists = await check_edition_exists(db, edition_key)
        if exists:
            logger.info(f"  ⏭️ Already exists: {edition_key}")
            already_exists += 1
            continue

        # Import edition
        success = await import_edition(db, blob_service, pdf_path, parsed, dry_run)
        if success:
            uploaded += 1
        else:
            errors += 1

        # Progress reporting (every 10 files)
        if idx % 10 == 0:
            logger.info(
                f"\n--- Progress: {idx}/{total_files} files processed "
                f"({uploaded} uploaded, {already_exists} skipped, {errors} errors) ---"
            )

    # Final statistics
    logger.info("\n" + "=" * 80)
    logger.info("Import Complete")
    logger.info("=" * 80)
    logger.info(f"Total files scanned:    {total_files}")
    logger.info(f"Already exists:         {already_exists}")
    logger.info(f"Successfully uploaded:  {uploaded}")
    logger.info(f"Errors:                 {errors}")
    logger.info(f"Skipped (unparseable):  {skipped}")

    if dry_run:
        logger.info("\n🔍 This was a DRY-RUN. Re-run without --dry-run to execute.")

    return ImportStats(total_files, already_exists, uploaded, errors, skipped)


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Import historical PDFs from OneDrive to Azure Blob Storage"
    )
    parser.add_argument(
        "--start-year",
        type=int,
        help="Start year (inclusive)",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        help="End year (inclusive)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview import without uploading or updating database",
    )

    args = parser.parse_args()

    try:
        stats = await run_import(
            start_year=args.start_year,
            end_year=args.end_year,
            dry_run=args.dry_run,
        )

        # Exit code based on errors
        if stats.errors > 0:
            exit(1)

    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Import interrupted by user")
        exit(130)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
