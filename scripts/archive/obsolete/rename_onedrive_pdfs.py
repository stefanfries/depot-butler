"""
Rename OneDrive PDFs to standardized format: YYYY-MM-DD_Edition-Name_II-YYYY.pdf

This script:
1. Scans OneDrive folder structure (year folders only)
2. Parses current filenames using flexible regex patterns
3. Generates standardized filenames matching daily workflow
4. Shows preview in dry-run mode (default)
5. Performs actual renames with --execute flag

Usage:
    python scripts/rename_onedrive_pdfs.py                # Dry-run (preview only)
    python scripts/rename_onedrive_pdfs.py --execute      # Actually rename files
"""

import asyncio
import re
import sys
from pathlib import Path
from typing import NamedTuple

from depotbutler.utils.logger import get_logger

# OneDrive folder path
ONEDRIVE_BASE = Path(
    r"C:\Users\stefa\OneDrive\Dokumente\Banken\DerAktionaer\Strategie_800-Prozent"
)

logger = get_logger(__name__)


class ParsedFilename(NamedTuple):
    """Parsed filename components."""

    date: str  # YYYY-MM-DD
    publication: str  # Publication name
    issue: str  # Issue number (2-digit)
    year: str  # Publication year (4-digit)
    pattern_name: str  # Which pattern matched


class RenameOperation(NamedTuple):
    """A file rename operation."""

    old_path: Path
    new_path: Path
    parsed: ParsedFilename


def analyze_filename(filename: str) -> ParsedFilename | None:
    """
    Parse filename to extract metadata using flexible regex patterns.

    Reuses the same patterns from analyze_onedrive_pdfs.py for consistency.
    """
    # Remove .pdf extension for pattern matching
    name_without_ext = filename.replace(".pdf", "")

    # Pattern definitions (same as analyze_onedrive_pdfs.py)
    patterns = {
        # Already standardized - just need to recognize them
        "standardized_800": r"^(\d{4}-\d{2}-\d{2})_Die-800%-Strategie_(\d{2})-(\d{4})$",
        "standardized_megatrend": r"^(\d{4}-\d{2}-\d{2})_Megatrend-Folger_(\d{2})-(\d{4})$",
        # Variations to rename
        "800_flexible_yyii": r"^(\d{4}-\d{2}-\d{2})\s+800[_-]?[Pp]rozent[_-]?[Ss]trategie[_ ](\d{4})$",
        "800_flexible_iy": r"^(\d{4}-\d{2}-\d{2})\s+800[_-]?[Pp]rozent[_-]?[Ss]trategie[_ ](\d{2})-(\d{4})$",
        "800_flexible_i_y": r"^(\d{4}-\d{2}-\d{2})\s+800[_-]?[Pp]rozent[_-]?[Ss]trategie[_ ](\d{2})_(\d{4})$",
        "800_short_yyii": r"^(\d{4}-\d{2}-\d{2})\s+800[_ ]?[Pp]rozent[_ ](\d{4})$",
        "megatrend_iy": r"^(\d{4}-\d{2}-\d{2})\s+[Mm]egatrend[_-][Ff]olger_(\d{2})-(\d{4})$",
        "megatrend_space_iy": r"^(\d{4}-\d{2}-\d{2})\s+[Mm]ega[Tt]rend-[Ff]olger_(\d{2})-(\d{4})$",
    }

    for pattern_name, regex in patterns.items():
        match = re.match(regex, name_without_ext)
        if match:
            date = match.group(1)

            # Already standardized files - return as-is
            if pattern_name.startswith("standardized"):
                if "800" in pattern_name:
                    publication = "Die-800%-Strategie"
                else:
                    publication = "Megatrend-Folger"
                issue = match.group(2)
                year = match.group(3)
            # Non-standardized patterns
            elif pattern_name.startswith("800"):
                publication = "Die-800%-Strategie"
                # Extract issue and year based on pattern format
                if pattern_name in ["800_flexible_yyii", "800_short_yyii"]:
                    # Concatenated format: YYII (4 digits) -> extract II and YYYY
                    yyii = match.group(2)  # All 4 digits
                    issue = yyii[2:]  # Last 2 digits = issue
                    year = f"20{yyii[:2]}"  # First 2 digits = year
                else:
                    # Separated format: II-YYYY or II_YYYY
                    issue = match.group(2)
                    year = match.group(3)
            else:
                # Megatrend patterns (always separated format)
                publication = "Megatrend-Folger"
                issue = match.group(2)
                year = match.group(3)

            return ParsedFilename(
                date=date,
                publication=publication,
                issue=issue,
                year=year,
                pattern_name=pattern_name,
            )

    return None


def generate_standardized_filename(parsed: ParsedFilename) -> str:
    """
    Generate standardized filename: YYYY-MM-DD_Edition-Name_II-YYYY.pdf

    Examples:
        2024-05-16_Die-800%-Strategie_20-2024.pdf
        2025-12-18_Megatrend-Folger_51-2025.pdf
    """
    # Ensure publication name uses hyphen (not space)
    publication = parsed.publication.replace(" ", "-")
    return f"{parsed.date}_{publication}_{parsed.issue}-{parsed.year}.pdf"


async def collect_rename_operations() -> list[RenameOperation]:
    """
    Scan OneDrive folder and collect all rename operations.

    Returns list of RenameOperation objects.
    """
    operations: list[RenameOperation] = []
    unparseable: list[Path] = []

    if not ONEDRIVE_BASE.exists():
        logger.error("OneDrive folder not found: %s", ONEDRIVE_BASE)
        return operations

    # Scan year folders only (2014-2025)
    for year_folder in sorted(ONEDRIVE_BASE.iterdir()):
        if not year_folder.is_dir():
            continue

        year_name = year_folder.name
        if not year_name.isdigit() or len(year_name) != 4:
            logger.debug("Skipping non-year folder: %s", year_name)
            continue

        logger.info("Scanning folder: %s", year_name)

        # Process all PDFs in this year folder
        for pdf_file in sorted(year_folder.glob("*.pdf")):
            parsed = analyze_filename(pdf_file.name)

            if parsed is None:
                unparseable.append(pdf_file)
                logger.warning("  ❌ Cannot parse: %s", pdf_file.name)
                continue

            # Generate standardized filename
            new_filename = generate_standardized_filename(parsed)
            new_path = pdf_file.parent / new_filename

            # Check if rename is needed
            if pdf_file.name == new_filename:
                logger.debug("  ✓ Already standardized: %s", pdf_file.name)
                continue

            operations.append(
                RenameOperation(
                    old_path=pdf_file,
                    new_path=new_path,
                    parsed=parsed,
                )
            )

    if unparseable:
        logger.warning("")
        logger.warning("⚠️  %d unparseable file(s) found:", len(unparseable))
        for path in unparseable:
            logger.warning("  - %s", path)

    return operations


def check_conflicts(
    operations: list[RenameOperation],
) -> tuple[list[RenameOperation], list[Path]]:
    """
    Check for naming conflicts (target filename already exists).

    Returns:
        - List of real conflicts (different files, can't resolve)
        - List of duplicates to delete (old versions that should be removed)
    """
    conflicts: list[RenameOperation] = []
    duplicates_to_delete: list[Path] = []

    for op in operations:
        if op.new_path.exists() and op.new_path != op.old_path:
            # This is a duplicate - the target already exists
            # The old file (op.old_path) should be deleted instead of renamed
            logger.info(
                "Duplicate found (will delete old version): %s",
                op.old_path.name,
            )
            duplicates_to_delete.append(op.old_path)

    return conflicts, duplicates_to_delete


def print_summary(
    operations: list[RenameOperation],
    conflicts: list[RenameOperation],
    duplicates: list[Path],
    dry_run: bool,
) -> None:
    """Print summary of rename operations."""
    logger.info("")
    logger.info("=" * 70)
    logger.info("RENAME SUMMARY")
    logger.info("=" * 70)

    if dry_run:
        logger.info("🔍 DRY-RUN MODE: No files will be renamed")
    else:
        logger.info("✅ EXECUTE MODE: Files will be renamed")

    logger.info("")
    logger.info("Total files to rename: %d", len(operations))

    if duplicates:
        logger.info("Duplicates to delete: %d", len(duplicates))

    # Group by pattern
    pattern_counts: dict[str, int] = {}
    for op in operations:
        pattern_counts[op.parsed.pattern_name] = (
            pattern_counts.get(op.parsed.pattern_name, 0) + 1
        )

    logger.info("")
    logger.info("Breakdown by pattern:")
    for pattern_name, count in sorted(pattern_counts.items()):
        percentage = (count / len(operations) * 100) if operations else 0
        logger.info("  - %s: %d (%.1f%%)", pattern_name, count, percentage)

    if conflicts:
        logger.info("")
        logger.error("⚠️  %d CONFLICT(S) DETECTED:", len(conflicts))
        for op in conflicts:
            logger.error("  - %s → %s", op.old_path.name, op.new_path.name)
            logger.error("    Target already exists: %s", op.new_path)
        logger.error("")
        logger.error("Please resolve conflicts manually before running with --execute")


def print_preview(operations: list[RenameOperation], max_display: int = 20) -> None:
    """Print preview of rename operations."""
    if not operations:
        logger.info("")
        logger.info("✅ All files are already standardized!")
        return

    logger.info("")
    logger.info("Preview of renames (first %d):", min(max_display, len(operations)))
    logger.info("")

    for i, op in enumerate(operations[:max_display], 1):
        logger.info("  [%d] %s", i, op.old_path.parent.name)
        logger.info("      OLD: %s", op.old_path.name)
        logger.info("      NEW: %s", op.new_path.name)
        logger.info("")

    if len(operations) > max_display:
        logger.info("  ... and %d more", len(operations) - max_display)


async def execute_renames(
    operations: list[RenameOperation], duplicates: list[Path]
) -> None:
    """Execute the rename operations and delete duplicates."""
    logger.info("")
    logger.info("Executing renames...")
    logger.info("")

    success_count = 0
    error_count = 0
    deleted_count = 0

    # First, delete duplicates
    if duplicates:
        logger.info("Deleting %d duplicate file(s)...", len(duplicates))
        for dup_path in duplicates:
            try:
                dup_path.unlink()
                deleted_count += 1
                logger.info("  🗑️  Deleted duplicate: %s", dup_path.name)
            except Exception as e:
                error_count += 1
                logger.error("  ❌ Failed to delete: %s", dup_path.name)
                logger.error("     Error: %s", e)
        logger.info("")

    # Then, rename files
    for i, op in enumerate(operations, 1):
        # Skip if this was a duplicate (already deleted)
        if op.old_path in duplicates:
            continue

        try:
            op.old_path.rename(op.new_path)
            success_count += 1
            if i <= 10 or i % 50 == 0:  # Show progress
                logger.info(
                    "  ✓ [%d/%d] Renamed: %s", i, len(operations), op.old_path.name
                )
        except Exception as e:
            error_count += 1
            logger.error(
                "  ❌ [%d/%d] Failed: %s", i, len(operations), op.old_path.name
            )
            logger.error("     Error: %s", e)

    logger.info("")
    logger.info("=" * 70)
    logger.info("EXECUTION COMPLETE")
    logger.info("=" * 70)
    logger.info("✅ Successfully renamed: %d", success_count)
    if deleted_count > 0:
        logger.info("🗑️  Duplicates deleted: %d", deleted_count)
    if error_count > 0:
        logger.error("❌ Errors: %d", error_count)
    logger.info("")


async def main() -> None:
    """Main entry point."""
    # Check for --execute flag
    execute = "--execute" in sys.argv
    dry_run = not execute

    logger.info("=" * 70)
    logger.info("OneDrive PDF Rename Tool")
    logger.info("=" * 70)
    logger.info("Scanning: %s", ONEDRIVE_BASE)
    logger.info("")

    # Collect rename operations
    operations = await collect_rename_operations()

    if not operations:
        logger.info("")
        logger.info("✅ All files are already standardized!")
        return

    # Check for conflicts
    conflicts, duplicates = check_conflicts(operations)

    # Print preview
    print_preview(operations)

    # Print summary
    print_summary(operations, conflicts, duplicates, dry_run)

    # Stop if conflicts found
    if conflicts:
        logger.error("")
        logger.error("Cannot proceed due to conflicts. Please resolve manually.")
        sys.exit(1)

    # Execute renames if requested
    if not dry_run:
        logger.info("")
        logger.info("Proceeding with renames...")
        await execute_renames(operations, duplicates)
    else:
        logger.info("")
        logger.info("To actually rename files, run with --execute flag:")
        logger.info("  python scripts/rename_onedrive_pdfs.py --execute")


if __name__ == "__main__":
    asyncio.run(main())
