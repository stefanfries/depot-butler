"""
Fix filename typos in OneDrive folder.

Some files have year typo: -2404.pdf instead of -2024.pdf
This script renames them to the correct format.

Usage:
    # Preview changes (dry-run)
    python scripts/fix_onedrive_filename_typos.py --dry-run

    # Execute renames
    python scripts/fix_onedrive_filename_typos.py --execute
"""

import argparse
from pathlib import Path

ONEDRIVE_BASE = Path(
    r"C:\Users\stefa\OneDrive\Dokumente\Banken\DerAktionaer\Strategie_800-Prozent"
)


def find_typo_files():
    """Find all files with year typo (2404 instead of 2024)."""
    typo_files = []

    for year_folder in sorted(ONEDRIVE_BASE.iterdir()):
        if not year_folder.is_dir():
            continue

        for pdf_file in year_folder.glob("*-2404.pdf"):
            typo_files.append(pdf_file)

    return typo_files


def fix_filename(old_path: Path, dry_run: bool = False) -> bool:
    """
    Rename file to fix year typo.

    Args:
        old_path: Path to file with typo
        dry_run: If True, only preview without renaming

    Returns:
        True if successful (or would be in dry-run)
    """
    new_name = old_path.name.replace("-2404.pdf", "-2024.pdf")
    new_path = old_path.parent / new_name

    if new_path.exists():
        print(f"  ⚠️  Target already exists: {new_name}")
        return False

    if dry_run:
        print(f"  ✓ Would rename: {old_path.name} → {new_name}")
        return True
    else:
        try:
            old_path.rename(new_path)
            print(f"  ✓ Renamed: {old_path.name} → {new_name}")
            return True
        except Exception as e:
            print(f"  ✗ Error: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Fix filename typos in OneDrive folder"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without renaming",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute renames (required for actual changes)",
    )

    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        print("Error: Must specify either --dry-run or --execute")
        return

    dry_run = args.dry_run

    print("=" * 80)
    print("FIX ONEDRIVE FILENAME TYPOS")
    print("=" * 80)
    print(f"Base folder: {ONEDRIVE_BASE}")

    if dry_run:
        print("Mode: DRY-RUN (preview only)")
    else:
        print("Mode: EXECUTE (will rename files)")

    print("\n" + "=" * 80)

    # Find files with typos
    typo_files = find_typo_files()

    if not typo_files:
        print("✓ No files with typos found!")
        return

    print(f"Found {len(typo_files)} files with year typo (2404 → 2024):\n")

    success_count = 0
    error_count = 0

    for file_path in sorted(typo_files):
        if fix_filename(file_path, dry_run):
            success_count += 1
        else:
            error_count += 1

    print("\n" + "=" * 80)
    print(f"Complete: {success_count} files processed, {error_count} errors")

    if dry_run:
        print("\nThis was a DRY-RUN. Use --execute to perform renames.")

    print("=" * 80)


if __name__ == "__main__":
    main()
