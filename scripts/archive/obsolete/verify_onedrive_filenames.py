"""
Verify OneDrive filename consistency.

Checks that all filenames have matching year at start and end:
- Start: YYYY-MM-DD_...
- End: ..._II-YYYY.pdf

Example:
  GOOD: 2024-01-25_Die-800%-Strategie_04-2024.pdf
  BAD:  2024-01-25_Die-800%-Strategie_04-2404.pdf

Usage:
    python scripts/verify_onedrive_filenames.py
"""

import re
from pathlib import Path

ONEDRIVE_BASE = Path(
    r"C:\Users\stefa\OneDrive\Dokumente\Banken\DerAktionaer\Strategie_800-Prozent"
)


def verify_filename(filename: str) -> tuple[bool, str, str, str]:
    """
    Verify filename year consistency.

    Args:
        filename: PDF filename to verify

    Returns:
        Tuple of (is_valid, start_year, end_year, error_message)
    """
    # Expected pattern: YYYY-MM-DD_Name_II-YYYY.pdf
    pattern = r"^(\d{4})-\d{2}-\d{2}_.*_\d{2}-(\d{4})\.pdf$"

    match = re.match(pattern, filename)
    if not match:
        return False, "", "", "Does not match expected pattern"

    start_year = match.group(1)
    end_year = match.group(2)

    if start_year != end_year:
        return False, start_year, end_year, f"Year mismatch: {start_year} vs {end_year}"

    return True, start_year, end_year, ""


def main():
    print("=" * 80)
    print("VERIFY ONEDRIVE FILENAME CONSISTENCY")
    print("=" * 80)
    print(f"Base folder: {ONEDRIVE_BASE}")
    print("Checking: Start year (YYYY-MM-DD) matches end year (II-YYYY.pdf)")
    print("=" * 80)

    total_files = 0
    valid_files = 0
    invalid_files = []
    unparseable_files = []

    # Scan all year folders
    for year_folder in sorted(ONEDRIVE_BASE.iterdir()):
        if not year_folder.is_dir():
            continue

        year_name = year_folder.name
        if not (year_name.isdigit() and len(year_name) == 4):
            continue

        print(f"\nChecking {year_name}/")
        folder_count = 0

        for pdf_file in sorted(year_folder.glob("*.pdf")):
            total_files += 1
            folder_count += 1

            is_valid, start_year, end_year, error = verify_filename(pdf_file.name)

            if error == "Does not match expected pattern":
                unparseable_files.append(pdf_file)
                print(f"  ⚠️  Unparseable: {pdf_file.name}")
            elif not is_valid:
                invalid_files.append((pdf_file, start_year, end_year, error))
                print(f"  ❌ {pdf_file.name}")
                print(f"     → {error}")
            else:
                valid_files += 1

        if folder_count > 0 and not any(
            f[0].parent == year_folder for f in invalid_files
        ):
            print(f"  ✓ All {folder_count} files valid")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total files scanned: {total_files}")
    print(f"Valid files:         {valid_files}")
    print(f"Invalid files:       {len(invalid_files)}")
    print(f"Unparseable files:   {len(unparseable_files)}")

    if invalid_files:
        print("\n" + "-" * 80)
        print("INVALID FILES (year mismatch):")
        print("-" * 80)
        for file_path, start_year, end_year, error in invalid_files:
            print(f"{file_path.parent.name}/{file_path.name}")
            print(f"  Start: {start_year}, End: {end_year}")

    if unparseable_files:
        print("\n" + "-" * 80)
        print("UNPARSEABLE FILES (wrong format):")
        print("-" * 80)
        for file_path in unparseable_files:
            print(f"{file_path.parent.name}/{file_path.name}")

    print("\n" + "=" * 80)
    if len(invalid_files) == 0 and len(unparseable_files) == 0:
        print("✅ ALL FILES VALID - Years are consistent!")
    else:
        print("⚠️  ISSUES FOUND - Review files above")
    print("=" * 80)


if __name__ == "__main__":
    main()
