"""
Tests for notification service archival status display.

Tests the new archival information display in daily report emails,
including the _get_archival_status() method and _build_success_section()
integration with archival data.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from depotbutler.models import Edition, PublicationResult, UploadResult
from depotbutler.services.notification_service import NotificationService


@pytest.fixture
def notification_service():
    """Create NotificationService instance with mocked email service."""
    mock_email_service = MagicMock()
    return NotificationService(email_service=mock_email_service, dry_run=True)


@pytest.fixture
def base_result():
    """Create a base PublicationResult for testing."""
    edition = Edition(
        title="Megatrend Folger 51/2025",
        details_url="https://example.com/details",
        download_url="https://example.com/download",
        publication_date="2025-11-23",
    )

    return PublicationResult(
        publication_id="megatrend-folger",
        publication_name="Megatrend Folger",
        success=True,
        edition=edition,
        email_result=True,
        upload_result=UploadResult(
            success=True,
            file_url="https://onedrive.live.com/view.aspx?resid=ABC123",
            file_id="ABC123",
        ),
        recipients_emailed=1,
        recipients_uploaded=1,
    )


# ============================================================================
# Tests for _get_archival_status()
# ============================================================================


def test_get_archival_status_successful(notification_service, base_result):
    """Test archival status display for successful archival."""
    base_result.archived = True
    base_result.blob_url = "https://depotbutlerarchive.blob.core.windows.net/editions/2025/megatrend-folger/file.pdf"
    base_result.archived_at = datetime.now(UTC)

    status = notification_service._get_archival_status(base_result)

    assert status == "<br>☁️ Archival: ✅ Archived to Blob Storage"


def test_get_archival_status_failed(notification_service, base_result):
    """Test archival status display for failed archival (non-blocking)."""
    base_result.archived = False

    status = notification_service._get_archival_status(base_result)

    assert status == "<br>☁️ Archival: ⚠️ Failed (workflow continued)"


def test_get_archival_status_not_attempted(notification_service, base_result):
    """Test archival status when blob storage not configured."""
    base_result.archived = None

    status = notification_service._get_archival_status(base_result)

    assert status == ""


def test_get_archival_status_none_defaults_to_not_attempted(
    notification_service, base_result
):
    """Test that missing archived field (None) is treated as not attempted."""
    # Don't set archived field at all (remains None from BaseModel)
    assert base_result.archived is None

    status = notification_service._get_archival_status(base_result)

    assert status == ""


# ============================================================================
# Tests for _build_success_section() with archival information
# ============================================================================


def test_build_success_section_with_archival(notification_service, base_result):
    """Test success section includes archival status when available."""
    base_result.archived = True
    base_result.blob_url = "https://depotbutlerarchive.blob.core.windows.net/editions/2025/megatrend-folger/file.pdf"

    html_parts = notification_service._build_success_section([base_result])
    html = "\n".join(html_parts)

    # Check all expected elements are present
    assert "<h3>✅ New Editions Processed</h3>" in html
    assert "Megatrend Folger 51/2025" in html
    assert "2025-11-23" in html
    assert "📧 Email: ✅ Sent" in html
    assert (
        "📎 <a href='https://onedrive.live.com/view.aspx?resid=ABC123'>View in OneDrive</a>"
        in html
    )
    assert "☁️ Archival: ✅ Archived to Blob Storage" in html


def test_build_success_section_with_failed_archival(notification_service, base_result):
    """Test success section shows failed archival warning."""
    base_result.archived = False

    html_parts = notification_service._build_success_section([base_result])
    html = "\n".join(html_parts)

    assert "☁️ Archival: ⚠️ Failed (workflow continued)" in html


def test_build_success_section_without_archival(notification_service, base_result):
    """Test success section when archival not configured (no archival line shown)."""
    base_result.archived = None

    html_parts = notification_service._build_success_section([base_result])
    html = "\n".join(html_parts)

    # Should NOT contain archival information
    assert "☁️ Archival" not in html
    assert "Blob Storage" not in html

    # But should still have other info
    assert "Megatrend Folger 51/2025" in html
    assert "📧 Email: ✅ Sent" in html


def test_build_success_section_multiple_results_mixed_archival(
    notification_service, base_result
):
    """Test success section with multiple publications with different archival states."""
    # First result: successful archival
    result1 = base_result.model_copy(deep=True)
    result1.archived = True
    result1.blob_url = "https://depotbutlerarchive.blob.core.windows.net/editions/2025/megatrend-folger/file1.pdf"

    # Second result: failed archival
    result2 = base_result.model_copy(deep=True)
    result2.edition.title = "DER AKTIONÄR E-Paper 52/2025"
    result2.publication_name = "DER AKTIONÄR E-Paper"
    result2.archived = False

    # Third result: no archival (blob storage not configured)
    result3 = base_result.model_copy(deep=True)
    result3.edition.title = "Test Publication 1/2025"
    result3.publication_name = "Test Publication"
    result3.archived = None

    html_parts = notification_service._build_success_section(
        [result1, result2, result3]
    )
    html = "\n".join(html_parts)

    # All three publications should be present
    assert "Megatrend Folger 51/2025" in html
    assert "DER AKTIONÄR E-Paper 52/2025" in html
    assert "Test Publication 1/2025" in html

    # Check archival statuses
    assert html.count("☁️ Archival: ✅ Archived to Blob Storage") == 1
    assert html.count("☁️ Archival: ⚠️ Failed (workflow continued)") == 1

    # For third publication (no archival), verify it doesn't have archival status
    # by counting total archival mentions - should be exactly 2 (one success, one failed)
    assert html.count("☁️ Archival") == 2


def test_build_success_section_email_disabled_with_archival(
    notification_service, base_result
):
    """Test success section when email disabled but archival succeeded."""
    base_result.email_result = None  # Email disabled
    base_result.archived = True

    html_parts = notification_service._build_success_section([base_result])
    html = "\n".join(html_parts)

    assert "📧 Email: ⏭️ Disabled" in html
    assert "☁️ Archival: ✅ Archived to Blob Storage" in html


def test_build_success_section_all_delivery_failed_but_archival_succeeded(
    notification_service, base_result
):
    """Test that archival success is shown even when email/OneDrive failed."""
    base_result.email_result = False
    base_result.upload_result.success = False
    base_result.archived = True

    html_parts = notification_service._build_success_section([base_result])
    html = "\n".join(html_parts)

    assert "📧 Email: ❌ Failed" in html
    assert "☁️ Archival: ✅ Archived to Blob Storage" in html


# ============================================================================
# Tests for HTML structure and formatting
# ============================================================================


def test_archival_status_appears_after_onedrive_link(notification_service, base_result):
    """Test that archival status appears after OneDrive link in HTML structure."""
    base_result.archived = True

    html_parts = notification_service._build_success_section([base_result])
    html = "\n".join(html_parts)

    # Find positions in HTML
    onedrive_pos = html.find("View in OneDrive")
    archival_pos = html.find("☁️ Archival")

    # Archival should come after OneDrive
    assert onedrive_pos < archival_pos


def test_archival_status_has_line_break_prefix(notification_service, base_result):
    """Test that archival status starts with <br> for proper formatting."""
    base_result.archived = True

    status = notification_service._get_archival_status(base_result)

    assert status.startswith("<br>")


def test_failed_archival_uses_warning_emoji(notification_service, base_result):
    """Test that failed archival uses warning emoji (⚠️) not error (❌)."""
    base_result.archived = False

    status = notification_service._get_archival_status(base_result)

    assert "⚠️" in status
    assert "❌" not in status


# ============================================================================
# Edge cases
# ============================================================================


def test_build_success_section_with_no_edition(notification_service):
    """Test success section handles missing edition gracefully."""
    result = PublicationResult(
        publication_id="test-pub",
        publication_name="Test Publication",
        success=True,
        edition=None,  # No edition
        archived=True,
    )

    html_parts = notification_service._build_success_section([result])
    html = "\n".join(html_parts)

    # Should use publication_name as fallback
    assert "Test Publication" in html
    assert "☁️ Archival: ✅ Archived to Blob Storage" in html


def test_build_success_section_with_archived_but_no_blob_url(
    notification_service, base_result
):
    """Test that archival success is shown even if blob_url is missing."""
    base_result.archived = True
    base_result.blob_url = None  # Missing blob_url

    html_parts = notification_service._build_success_section([base_result])
    html = "\n".join(html_parts)

    # Should still show archival success
    assert "☁️ Archival: ✅ Archived to Blob Storage" in html


def test_build_success_section_empty_list(notification_service):
    """Test success section with empty results list."""
    html_parts = notification_service._build_success_section([])
    html = "\n".join(html_parts)

    # Should only have the header
    assert "<h3>✅ New Editions Processed</h3>" in html
    assert html.count("<div") == 0  # No result divs
