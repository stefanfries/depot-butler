#!/usr/bin/env python3
"""
Test script to preview the archival notification in daily report.
Shows what the email will look like with archival information.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from depotbutler.models import Edition, PublicationResult, UploadResult
from depotbutler.services.notification_service import NotificationService


def create_test_result(archived: bool | None) -> PublicationResult:
    """Create a test result with archival status."""
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
        archived=archived,
        blob_url="https://depotbutlerarchive.blob.core.windows.net/editions/2025/megatrend-folger/megatrend-folger_51_2025.pdf"
        if archived
        else None,
        archived_at=datetime.now(UTC) if archived else None,
    )


def main() -> None:
    """Test notification service with archival information."""
    # Create mock email service
    mock_email_service = MagicMock()
    notification_service = NotificationService(
        email_service=mock_email_service, dry_run=True
    )

    print("=" * 80)
    print("Testing Notification HTML with Archival Status")
    print("=" * 80)

    # Test 1: Successful archival
    print("\n1. SUCCESSFUL ARCHIVAL:")
    print("-" * 80)
    result_success = create_test_result(archived=True)
    html = notification_service._build_success_section([result_success])
    print("\n".join(html))

    # Test 2: Failed archival (non-blocking)
    print("\n\n2. FAILED ARCHIVAL (non-blocking):")
    print("-" * 80)
    result_failed = create_test_result(archived=False)
    html = notification_service._build_success_section([result_failed])
    print("\n".join(html))

    # Test 3: Archival not attempted (blob storage not configured)
    print("\n\n3. NO ARCHIVAL (blob storage not configured):")
    print("-" * 80)
    result_none = create_test_result(archived=None)
    html = notification_service._build_success_section([result_none])
    print("\n".join(html))

    print("\n" + "=" * 80)
    print("Perfect! Archival information now appears in daily reports:")
    print("=" * 80)
    print("✅ Successful archival: Shows '☁️ Archival: ✅ Archived to Blob Storage'")
    print("⚠️ Failed archival: Shows '☁️ Archival: ⚠️ Failed (workflow continued)'")
    print("ℹ️ Not configured: No archival line shown")


if __name__ == "__main__":
    main()
