"""
Test PDF parsing capability with pdfplumber.

This script validates that we can:
1. Extract tables from Megatrend-Folger PDFs
2. Parse instrument data (WKN, name, quantity, prices)
3. Handle German number formats
4. Identify table structure changes across years

Run: uv run python scripts/validation/test_pdf_parsing.py
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from decimal import Decimal

import pdfplumber

from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


def test_pdf_extraction(pdf_path: Path):
    """Test extraction from a single PDF."""
    logger.info(f"Testing PDF: {pdf_path.name}")

    try:
        with pdfplumber.open(pdf_path) as pdf:
            logger.info(f"Pages: {len(pdf.pages)}")

            # Test each page
            for i, page in enumerate(pdf.pages, 1):
                logger.info(f"\nPage {i}:")

                # Extract tables
                tables = page.extract_tables()
                logger.info(f"  Tables found: {len(tables)}")

                for j, table in enumerate(tables, 1):
                    logger.info(f"\n  Table {j}: {len(table)} rows")

                    # Show first few rows
                    for row_idx, row in enumerate(table[:5], 1):
                        logger.info(f"    Row {row_idx}: {row}")

                    if len(table) > 5:
                        logger.info(f"    ... ({len(table) - 5} more rows)")

        logger.info(f"✅ Successfully extracted from {pdf_path.name}")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to extract from {pdf_path.name}: {e}")
        return False


def parse_german_number(value: str) -> Decimal | None:
    """Parse German number format (1.234,56 -> 1234.56)."""
    if not value or value == "-":
        return None

    try:
        # Remove spaces and thousand separators
        cleaned = value.replace(" ", "").replace(".", "")
        # Replace comma with period
        cleaned = cleaned.replace(",", ".")
        return Decimal(cleaned)
    except Exception:
        return None


def test_musterdepot_parsing(pdf_path: Path):
    """Attempt to parse Musterdepot table from PDF."""
    logger.info(f"\nParsing Musterdepot from: {pdf_path.name}")

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()

                for table in tables:
                    # Look for Musterdepot table (has WKN/ISIN columns)
                    if len(table) < 2:
                        continue

                    header = table[0]

                    # Check if this looks like Musterdepot
                    has_wkn = any(
                        "WKN" in str(cell).upper() if cell else False for cell in header
                    )
                    has_isin = any(
                        "ISIN" in str(cell).upper() if cell else False
                        for cell in header
                    )

                    if has_wkn or has_isin:
                        logger.info("✅ Found Musterdepot table!")
                        logger.info(f"Header: {header}")
                        logger.info(f"Data rows: {len(table) - 1}")

                        # Try parsing first data row
                        if len(table) > 1:
                            sample_row = table[1]
                            logger.info(f"Sample row: {sample_row}")

                            # Attempt to identify columns
                            logger.info("\nColumn analysis:")
                            for idx, (header_cell, data_cell) in enumerate(
                                zip(header, sample_row)
                            ):
                                logger.info(
                                    f"  Col {idx}: '{header_cell}' = '{data_cell}'"
                                )

                        return True

        logger.warning("⚠️ No Musterdepot table found in PDF")
        return False

    except Exception as e:
        logger.error(f"❌ Failed to parse Musterdepot: {e}")
        return False


def test_german_number_parsing():
    """Test German number format parsing."""
    logger.info("\nTesting German number format parsing:")

    test_cases = [
        ("1.234,56", Decimal("1234.56")),
        ("123,45", Decimal("123.45")),
        ("12,3", Decimal("12.3")),
        ("1,00", Decimal("1.00")),
        ("-", None),
        ("", None),
    ]

    passed = 0
    for input_val, expected in test_cases:
        result = parse_german_number(input_val)
        status = "✅" if result == expected else "❌"
        logger.info(f"  {status} '{input_val}' -> {result} (expected: {expected})")
        if result == expected:
            passed += 1

    logger.info(f"German number parsing: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


def main():
    """Run PDF parsing validation."""
    logger.info("=" * 60)
    logger.info("PDF PARSING VALIDATION")
    logger.info("=" * 60)

    # Test German number parsing
    test_german_number_parsing()

    # Look for sample PDFs in data/tmp/
    data_dir = Path(__file__).parent.parent.parent / "data" / "tmp"
    pdf_files = list(data_dir.glob("*.pdf"))

    if not pdf_files:
        logger.warning("\n⚠️ No PDF files found in data/tmp/")
        logger.info("\nTo test PDF parsing:")
        logger.info("1. Download 3-5 sample PDFs from different years")
        logger.info("2. Place them in data/tmp/")
        logger.info("3. Re-run this script")
        return

    logger.info(f"\nFound {len(pdf_files)} PDF files to test")

    # Test extraction on each PDF
    success_count = 0
    for pdf_path in sorted(pdf_files)[:5]:  # Test first 5
        if test_pdf_extraction(pdf_path):
            success_count += 1

        # Try parsing Musterdepot
        test_musterdepot_parsing(pdf_path)
        logger.info("-" * 60)

    logger.info("=" * 60)
    logger.info("VALIDATION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"PDFs processed: {success_count}/{min(len(pdf_files), 5)}")
    logger.info("\nNext steps:")
    logger.info("1. Review table structure and adjust parsing logic")
    logger.info("2. Map columns to domain model (WKN, name, quantity, etc.)")
    logger.info("3. Handle multiple table formats if needed")
    logger.info("4. Proceed to test_blob_storage.py")


if __name__ == "__main__":
    main()
