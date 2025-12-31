"""
Analyze PDF files in OneDrive folder to understand naming conventions.

This script scans the local OneDrive folder structure and analyzes all PDF
filenames to identify naming patterns, inconsistencies, and prepare for
standardization before import.

Usage:
    uv run python scripts/analyze_onedrive_pdfs.py
"""

import re
from collections import defaultdict
from pathlib import Path

from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


def analyze_filename(filename: str) -> dict[str, str | None]:
    """
    Parse a PDF filename and extract components.

    Returns:
        Dictionary with parsed components and detected pattern type
    """
    # Remove .pdf extension
    name = filename.replace(".pdf", "")

    # Try different patterns
    patterns = {
        # YYYY-MM-DD 800[_-]prozent[_-]strategie_YYII (flexible separators, concatenated year+issue)
        # Matches all variations: 800_prozent_strategie, 800-prozent-strategie, 800_Prozent_Strategie, etc.
        "800_flexible_yyii": r"^(\d{4}-\d{2}-\d{2})\s+800[_-]?[Pp]rozent[_-]?[Ss]trategie[_ ](\d{2})(\d{2})$",
        # YYYY-MM-DD 800_prozent_YYII (just 800_prozent without "strategie")
        "800_short_yyii": r"^(\d{4}-\d{2}-\d{2})\s+800_prozent_(\d{2})(\d{2})$",
        # YYYY-MM-DD 800[_-]Prozent[_-]Strategie_II-YYYY (hyphen-separated issue-year)
        "800_flexible_iy": r"^(\d{4}-\d{2}-\d{2})\s+800[_-]?[Pp]rozent[_-]?[Ss]trategie[_ ](\d{2})-(\d{4})$",
        # YYYY-MM-DD 800[_-]Prozent[_-]Strategie_II_YYYY (underscore-separated issue_year)
        "800_flexible_i_y": r"^(\d{4}-\d{2}-\d{2})\s+800[_-]?[Pp]rozent[_-]?[Ss]trategie[_ ](\d{2})_(\d{4})$",
        # YYYY-MM-DD MegaTrend-Folger_II-YYYY (space separator, capital T)
        "megatrend_space_iy": r"^(\d{4}-\d{2}-\d{2})\s+[Mm]ega[Tt]rend-[Ff]olger_(\d{2})-(\d{4})$",
        # YYYY-MM-DD megatrend_folger_YYII (space, underscore, concatenated)
        "megatrend_space_yyii": r"^(\d{4}-\d{2}-\d{2})\s+megatrend_folger_(\d{2})(\d{2})$",
        # YYYY-MM-DD_Megatrend-Folger_II-YYYY (hyphen format, issue-year)
        "megatrend_iy": r"^(\d{4}-\d{2}-\d{2})_([Mm]egatrend[- ]?[Ff]olger)_(\d{2})-(\d{2,4})$",
        # YYYY-MM-DD_Megatrend-Folger_YYYY-II (hyphen format, year-issue)
        "megatrend_yi": r"^(\d{4}-\d{2}-\d{2})_([Mm]egatrend[- ]?[Ff]olger)_(\d{2,4})-(\d{2})$",
        # YYYY-MM-DD_800-Prozent-Strategie_II-YYYY
        "800_iy": r"^(\d{4}-\d{2}-\d{2})_(800[- ]?[Pp]rozent[- ]?[Ss]trategie|Die[- ]800%-Strategie)_(\d{2})-(\d{2,4})$",
        # YYYY-MM-DD_800-Prozent-Strategie_YYYY-II
        "800_yi": r"^(\d{4}-\d{2}-\d{2})_(800[- ]?[Pp]rozent[- ]?[Ss]trategie|Die[- ]800%-Strategie)_(\d{2,4})-(\d{2})$",
        # Fallback: just extract date if present
        "date_only": r"^(\d{4}-\d{2}-\d{2})[\s_](.+)$",
    }

    result = {
        "original": filename,
        "date": None,
        "publication": None,
        "issue": None,
        "year": None,
        "pattern": None,
    }

    for pattern_name, pattern_regex in patterns.items():
        match = re.match(pattern_regex, name)
        if match:
            result["pattern"] = pattern_name
            result["date"] = match.group(1)

            if pattern_name in [
                "800_space_yyii_lower",
                "800_capital_yyii",
                "800_mixed_yyii",
                "800_flexible_yyii",
                "800_short_yyii",
            ]:
                result["publication"] = "Die 800%-Strategie"
                year_2digit = match.group(2)
                issue_2digit = match.group(3)
                # Convert 2-digit year to 4-digit (14 -> 2014, 25 -> 2025)
                year_int = int(year_2digit)
                result["year"] = str(2000 + year_int)  # Assumes 2000-2099
                result["issue"] = issue_2digit

            elif pattern_name in ["800_flexible_iy", "800_flexible_i_y"]:
                result["publication"] = "Die 800%-Strategie"
                result["issue"] = match.group(2)
                result["year"] = match.group(3)

            elif pattern_name == "megatrend_space_iy":
                result["publication"] = "Megatrend Folger"
                result["issue"] = match.group(2)
                result["year"] = match.group(3)

            elif pattern_name == "megatrend_space_yyii":
                result["publication"] = "Megatrend Folger"
                year_2digit = match.group(2)
                issue_2digit = match.group(3)
                year_int = int(year_2digit)
                result["year"] = str(2000 + year_int)
                result["issue"] = issue_2digit

            elif pattern_name in ["megatrend_iy", "megatrend_yi"]:
                result["publication"] = "Megatrend Folger"
                if pattern_name == "megatrend_iy":
                    result["issue"] = match.group(3)
                    result["year"] = match.group(4)
                else:  # megatrend_yi
                    result["year"] = match.group(3)
                    result["issue"] = match.group(4)

            elif pattern_name in ["800_iy", "800_yi"]:
                result["publication"] = "Die 800%-Strategie"
                if pattern_name == "800_iy":
                    result["issue"] = match.group(3)
                    result["year"] = match.group(4)
                else:  # 800_yi
                    result["year"] = match.group(3)
                    result["issue"] = match.group(4)

            elif pattern_name == "date_only":
                result["publication"] = "Unknown"

            break

    if result["pattern"] is None:
        result["pattern"] = "unparseable"

    return result


def scan_onedrive_folder(base_path: Path) -> dict[str, list[dict]]:
    """
    Scan OneDrive folder structure and analyze all PDF files.

    Returns:
        Dictionary mapping year folders to list of file analysis results
    """
    if not base_path.exists():
        logger.error("Base path does not exist: %s", base_path)
        return {}

    results: dict[str, list[dict]] = defaultdict(list)

    logger.info("Scanning OneDrive folder: %s", base_path)

    # Iterate through year folders only (skip special folders)
    for year_folder in sorted(base_path.iterdir()):
        if not year_folder.is_dir():
            continue

        year_name = year_folder.name
        # Only process folders with 4-digit year names
        if not year_name.isdigit() or len(year_name) != 4:
            logger.debug("  Skipping non-year folder: %s", year_name)
            continue

        logger.info("  Scanning folder: %s", year_name)

        # Find all PDFs in this year folder
        pdf_files = list(year_folder.glob("*.pdf"))
        logger.info("    Found %d PDF files", len(pdf_files))

        for pdf_file in sorted(pdf_files):
            analysis = analyze_filename(pdf_file.name)
            analysis["folder"] = year_name
            analysis["full_path"] = str(pdf_file)
            results[year_name].append(analysis)

    return results


def print_analysis_report(results: dict[str, list[dict]]) -> None:
    """Print a comprehensive analysis report."""
    total_files = sum(len(files) for files in results.values())
    logger.info("\n" + "=" * 80)
    logger.info("ANALYSIS REPORT")
    logger.info("=" * 80)
    logger.info("Total files scanned: %d", total_files)
    logger.info("Year folders: %s", ", ".join(sorted(results.keys())))

    # Count patterns
    pattern_counts: dict[str, int] = defaultdict(int)
    for files in results.values():
        for file_info in files:
            pattern_counts[file_info["pattern"]] += 1

    logger.info("\n--- Naming Pattern Distribution ---")
    for pattern, count in sorted(pattern_counts.items(), key=lambda x: -x[1]):
        percentage = (count / total_files * 100) if total_files > 0 else 0
        logger.info("  %s: %d (%.1f%%)", pattern, count, percentage)

    # Show examples of each pattern
    logger.info("\n--- Pattern Examples ---")
    examples_shown: set[str] = set()
    for year_name in sorted(results.keys()):
        for file_info in results[year_name]:
            pattern = file_info["pattern"]
            if pattern not in examples_shown:
                logger.info("\n  Pattern: %s", pattern)
                logger.info("    Original: %s", file_info["original"])
                logger.info("    Date: %s", file_info["date"])
                logger.info("    Publication: %s", file_info["publication"])
                logger.info("    Issue: %s", file_info["issue"])
                logger.info("    Year: %s", file_info["year"])
                examples_shown.add(pattern)

    # Show problematic files (unparseable or inconsistent)
    logger.info("\n--- Problematic Files ---")
    unparseable_files = []
    inconsistent_files = []

    for year_name in sorted(results.keys()):
        for file_info in results[year_name]:
            if file_info["pattern"] == "unparseable":
                unparseable_files.append(file_info)
            elif file_info["year"] and len(file_info["year"]) == 2:
                # 2-digit year should be standardized to 4-digit
                inconsistent_files.append(file_info)

    if unparseable_files:
        logger.info("\n  Unparseable files (%d):", len(unparseable_files))
        for file_info in unparseable_files[:10]:  # Show first 10
            logger.info(
                "    %s (folder: %s)", file_info["original"], file_info["folder"]
            )
        if len(unparseable_files) > 10:
            logger.info("    ... and %d more", len(unparseable_files) - 10)
    else:
        logger.info("\n  ✅ No unparseable files!")

    if inconsistent_files:
        logger.info("\n  Files with 2-digit years (%d):", len(inconsistent_files))
        for file_info in inconsistent_files[:5]:  # Show first 5
            logger.info("    %s (year: %s)", file_info["original"], file_info["year"])
        if len(inconsistent_files) > 5:
            logger.info("    ... and %d more", len(inconsistent_files) - 5)
    else:
        logger.info("\n  ✅ All years are 4-digit!")

    # Year distribution
    logger.info("\n--- Files by Year Folder ---")
    for year_name in sorted(results.keys()):
        logger.info("  %s: %d files", year_name, len(results[year_name]))

    logger.info("\n" + "=" * 80)


def main() -> None:
    """Main entry point."""
    base_path = Path(
        r"C:\Users\stefa\OneDrive\Dokumente\Banken\DerAktionaer\Strategie_800-Prozent"
    )

    logger.info("OneDrive PDF Analysis Tool")
    logger.info("Target folder: %s\n", base_path)

    # Scan and analyze
    results = scan_onedrive_folder(base_path)

    if not results:
        logger.error("No files found or folder doesn't exist!")
        return

    # Print report
    print_analysis_report(results)

    # Save detailed results to file for review
    output_file = Path("data/tmp/onedrive_analysis.txt")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("DETAILED FILE ANALYSIS\n")
        f.write("=" * 80 + "\n\n")

        for year_name in sorted(results.keys()):
            f.write(f"\n=== Year: {year_name} ===\n\n")
            for file_info in results[year_name]:
                f.write(f"File: {file_info['original']}\n")
                f.write(f"  Pattern: {file_info['pattern']}\n")
                f.write(f"  Date: {file_info['date']}\n")
                f.write(f"  Publication: {file_info['publication']}\n")
                f.write(f"  Issue: {file_info['issue']}\n")
                f.write(f"  Year: {file_info['year']}\n")
                f.write(f"  Path: {file_info['full_path']}\n")
                f.write("\n")

    logger.info("\n✅ Detailed analysis saved to: %s", output_file)


if __name__ == "__main__":
    main()
