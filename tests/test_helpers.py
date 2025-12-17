"""Tests for helper functions (utils/helpers.py)."""

import pytest

from depotbutler.models import Edition
from depotbutler.utils.helpers import create_filename


def test_create_filename_normal_issue():
    """Test filename generation for normal issue (e.g., DER AKTIONÄR 05/25)."""
    edition = Edition(
        title="DER AKTIONÄR 05/25",
        details_url="https://example.com/details",
        download_url="https://example.com/download",
        publication_date="2025-11-05",
    )
    filename = create_filename(edition)
    assert filename == "2025-11-05_Der-Aktionär_05-25.pdf"


def test_create_filename_edition_issue():
    """Test filename generation for edition issue (e.g., DER AKTIONÄR EDITION 01/26)."""
    edition = Edition(
        title="DER AKTIONÄR EDITION 01/26",
        details_url="https://example.com/details",
        download_url="https://example.com/download",
        publication_date="2025-12-20",
    )
    filename = create_filename(edition)
    assert filename == "2025-12-20_Der-Aktionär-Edition_01-26.pdf"


def test_create_filename_double_issue():
    """Test filename generation for double issue (e.g., DER AKTIONÄR 52/25 + 01/26)."""
    edition = Edition(
        title="DER AKTIONÄR 52/25 + 01/26",
        details_url="https://example.com/details",
        download_url="https://example.com/download",
        publication_date="2025-12-17",
    )
    filename = create_filename(edition)
    assert filename == "2025-12-17_Der-Aktionär_52-25+01-26.pdf"


def test_create_filename_double_issue_with_extra_spaces():
    """Test filename generation with extra spaces around + sign."""
    edition = Edition(
        title="DER AKTIONÄR 52/25  +  01/26",
        details_url="https://example.com/details",
        download_url="https://example.com/download",
        publication_date="2025-12-17",
    )
    filename = create_filename(edition)
    assert filename == "2025-12-17_Der-Aktionär_52-25+01-26.pdf"


def test_create_filename_lowercase_title():
    """Test that lowercase titles are properly title-cased."""
    edition = Edition(
        title="der aktionär 05/25",
        details_url="https://example.com/details",
        download_url="https://example.com/download",
        publication_date="2025-11-05",
    )
    filename = create_filename(edition)
    assert filename == "2025-11-05_Der-Aktionär_05-25.pdf"


def test_create_filename_different_publication():
    """Test filename generation for different publication name."""
    edition = Edition(
        title="Megatrend Folger 12/25",
        details_url="https://example.com/details",
        download_url="https://example.com/download",
        publication_date="2025-12-01",
    )
    filename = create_filename(edition)
    assert filename == "2025-12-01_Megatrend-Folger_12-25.pdf"


def test_create_filename_multi_word_publication():
    """Test filename generation with multi-word publication name."""
    edition = Edition(
        title="Hot Stock Report Edition 03/26",
        details_url="https://example.com/details",
        download_url="https://example.com/download",
        publication_date="2026-03-01",
    )
    filename = create_filename(edition)
    assert filename == "2026-03-01_Hot-Stock-Report-Edition_03-26.pdf"


def test_create_filename_preserves_date_format():
    """Test that date format is preserved exactly as provided."""
    edition = Edition(
        title="DER AKTIONÄR 05/25",
        details_url="https://example.com/details",
        download_url="https://example.com/download",
        publication_date="2025-05-15",
    )
    filename = create_filename(edition)
    assert filename.startswith("2025-05-15_")


def test_create_filename_fallback_logic():
    """Test fallback logic for titles that don't match expected pattern."""
    edition = Edition(
        title="Special Report",
        details_url="https://example.com/details",
        download_url="https://example.com/download",
        publication_date="2025-12-17",
    )
    filename = create_filename(edition)
    # Fallback should still produce valid filename
    assert filename.startswith("2025-12-17_")
    assert filename.endswith(".pdf")


def test_create_filename_with_umlauts():
    """Test filename generation with German umlauts."""
    edition = Edition(
        title="DER AKTIONÄR 05/25",
        details_url="https://example.com/details",
        download_url="https://example.com/download",
        publication_date="2025-11-05",
    )
    filename = create_filename(edition)
    # Title.title() preserves umlauts correctly
    assert "Aktionär" in filename


def test_create_filename_filesystem_safe():
    """Test that generated filenames are filesystem-safe."""
    edition = Edition(
        title="DER AKTIONÄR 52/25 + 01/26",
        details_url="https://example.com/details",
        download_url="https://example.com/download",
        publication_date="2025-12-17",
    )
    filename = create_filename(edition)

    # Check no forbidden characters (except + which is allowed)
    forbidden = ["<", ">", ":", '"', "\\", "|", "?", "*"]
    for char in forbidden:
        assert char not in filename

    # Slashes should be replaced with hyphens
    assert "/" not in filename or filename.count("/") == 0
