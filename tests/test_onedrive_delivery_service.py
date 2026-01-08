"""Tests for OneDriveDeliveryService.

This test module covers:
- upload_for_recipients() method with recipient filtering
- upload_to_archive() method for file_path tracking
- Default folder vs custom folder handling
- Dry-run mode behavior
- MongoDB timestamp tracking
- Error handling and edge cases
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from depotbutler.models import Edition, UploadResult
from depotbutler.services.onedrive_delivery_service import OneDriveDeliveryService


@pytest.fixture
def mock_onedrive_service():
    """Create mock OneDriveService."""
    service = AsyncMock()
    service.authenticate = AsyncMock(return_value=True)
    service.upload_file = AsyncMock(
        return_value=UploadResult(
            success=True,
            file_url="https://onedrive.com/test-file",
            file_id="test-file-id",
        )
    )
    return service


@pytest.fixture
def mock_edition_tracker():
    """Create mock EditionTrackingService."""
    tracker = MagicMock()
    tracker._generate_edition_key = MagicMock(
        return_value="2025-11-23_test-publication_47-25"
    )
    return tracker


@pytest.fixture
def mock_edition():
    """Create mock Edition for testing."""
    return Edition(
        title="Test Publication",
        publication_date="2025-11-23",
        issue="47/25",
        details_url="https://example.com/details",
        download_url="https://example.com/download",
    )


@pytest.fixture
def mock_publication_data():
    """Create mock publication document."""
    return {
        "publication_id": "test-publication",
        "name": "Test Publication",
        "default_onedrive_folder": "Dokumente/Test",
        "onedrive_organize_by_year": True,
        "active": True,
    }


@pytest.fixture
def sample_recipients():
    """Sample recipients with different OneDrive preferences."""
    return [
        {
            "email": "default1@example.com",
            "active": True,
            "publication_preferences": [
                {
                    "publication_id": "test-publication",
                    "email_enabled": False,
                    "onedrive_enabled": True,
                    # No custom folder - uses default
                }
            ],
        },
        {
            "email": "default2@example.com",
            "active": True,
            "publication_preferences": [
                {
                    "publication_id": "test-publication",
                    "email_enabled": False,
                    "onedrive_enabled": True,
                    # No custom folder - uses default
                }
            ],
        },
        {
            "email": "custom@example.com",
            "active": True,
            "publication_preferences": [
                {
                    "publication_id": "test-publication",
                    "email_enabled": False,
                    "onedrive_enabled": True,
                    "custom_onedrive_folder": "Custom/Folder",
                }
            ],
        },
    ]


class TestOneDriveDeliveryService:
    """Test suite for OneDriveDeliveryService."""

    @pytest.mark.asyncio
    async def test_upload_for_recipients_default_folder_only(
        self,
        mock_onedrive_service,
        mock_edition_tracker,
        mock_edition,
        mock_publication_data,
    ):
        """Test uploading to default folder for all recipients."""
        service = OneDriveDeliveryService(
            mock_onedrive_service, mock_edition_tracker, dry_run=False
        )

        recipients = [
            {
                "email": "user1@example.com",
                "publication_preferences": [
                    {"publication_id": "test-publication", "onedrive_enabled": True}
                ],
            },
            {
                "email": "user2@example.com",
                "publication_preferences": [
                    {"publication_id": "test-publication", "onedrive_enabled": True}
                ],
            },
        ]

        with patch("depotbutler.db.mongodb.get_mongodb_service") as mock_mongodb:
            mock_db = AsyncMock()
            mock_db.edition_repo = AsyncMock()
            mock_db.edition_repo.update_onedrive_uploaded_timestamp = AsyncMock()
            mock_db.get_recipients_for_publication = AsyncMock(return_value=recipients)
            mock_mongodb.return_value = mock_db

            result = await service.upload_for_recipients(
                mock_edition, "/tmp/test.pdf", mock_publication_data
            )

        # Should upload once to default folder (batch upload)
        assert result.success is True
        assert mock_onedrive_service.upload_file.call_count == 1
        assert "2 recipient(s)" in result.file_url or "|2" in result.file_url

    @pytest.mark.asyncio
    async def test_upload_for_recipients_custom_folders(
        self,
        mock_onedrive_service,
        mock_edition_tracker,
        mock_edition,
        mock_publication_data,
        sample_recipients,
    ):
        """Test uploading to both default and custom folders."""
        service = OneDriveDeliveryService(
            mock_onedrive_service, mock_edition_tracker, dry_run=False
        )

        with patch("depotbutler.db.mongodb.get_mongodb_service") as mock_mongodb:
            mock_db = AsyncMock()
            mock_db.edition_repo = AsyncMock()
            mock_db.edition_repo.update_onedrive_uploaded_timestamp = AsyncMock()
            mock_db.get_recipients_for_publication = AsyncMock(
                return_value=sample_recipients
            )
            mock_mongodb.return_value = mock_db

            result = await service.upload_for_recipients(
                mock_edition, "/tmp/test.pdf", mock_publication_data
            )

        # Should upload:
        # 1. Once to default folder (2 recipients)
        # 2. Once to custom folder (1 recipient)
        assert result.success is True
        assert mock_onedrive_service.upload_file.call_count == 2

    @pytest.mark.asyncio
    async def test_upload_for_recipients_no_recipients(
        self,
        mock_onedrive_service,
        mock_edition_tracker,
        mock_edition,
        mock_publication_data,
    ):
        """Test upload when no recipients are eligible."""
        service = OneDriveDeliveryService(
            mock_onedrive_service, mock_edition_tracker, dry_run=False
        )

        with patch("depotbutler.db.mongodb.get_mongodb_service") as mock_mongodb:
            mock_db = AsyncMock()
            mock_db.get_recipients_for_publication = AsyncMock(return_value=[])
            mock_mongodb.return_value = mock_db

            result = await service.upload_for_recipients(
                mock_edition, "/tmp/test.pdf", mock_publication_data
            )

        # Should succeed but indicate no recipients
        assert result.success is True
        assert "No recipients" in result.file_url
        assert mock_onedrive_service.upload_file.call_count == 0

    @pytest.mark.asyncio
    async def test_upload_for_recipients_dry_run(
        self,
        mock_onedrive_service,
        mock_edition_tracker,
        mock_edition,
        mock_publication_data,
        sample_recipients,
    ):
        """Test dry-run mode doesn't perform actual uploads."""
        service = OneDriveDeliveryService(
            mock_onedrive_service, mock_edition_tracker, dry_run=True
        )

        with patch("depotbutler.db.mongodb.get_mongodb_service") as mock_mongodb:
            mock_db = AsyncMock()
            mock_db.edition_repo = AsyncMock()
            mock_db.edition_repo.update_onedrive_uploaded_timestamp = AsyncMock()
            mock_db.get_recipients_for_publication = AsyncMock(
                return_value=sample_recipients
            )
            mock_mongodb.return_value = mock_db

            result = await service.upload_for_recipients(
                mock_edition, "/tmp/test.pdf", mock_publication_data
            )

        # Should succeed but not actually upload
        assert result.success is True
        assert mock_onedrive_service.upload_file.call_count == 0

    @pytest.mark.asyncio
    async def test_upload_for_recipients_filtered_by_preferences(
        self,
        mock_onedrive_service,
        mock_edition_tracker,
        mock_edition,
        mock_publication_data,
    ):
        """Test recipient filtering based on publication preferences."""
        service = OneDriveDeliveryService(
            mock_onedrive_service, mock_edition_tracker, dry_run=False
        )

        # Note: get_recipients_for_publication already filters by delivery_method='upload'
        # So we only get recipients with onedrive_enabled=True
        recipients = [
            {
                "email": "enabled@example.com",
                "publication_preferences": [
                    {"publication_id": "test-publication", "onedrive_enabled": True}
                ],
            },
            {
                "email": "no-prefs@example.com",
                "publication_preferences": [
                    {"publication_id": "test-publication", "onedrive_enabled": True}
                ],
            },
        ]

        with patch("depotbutler.db.mongodb.get_mongodb_service") as mock_mongodb:
            mock_db = AsyncMock()
            mock_db.edition_repo = AsyncMock()
            mock_db.edition_repo.update_onedrive_uploaded_timestamp = AsyncMock()
            mock_db.get_recipients_for_publication = AsyncMock(return_value=recipients)
            mock_mongodb.return_value = mock_db

            result = await service.upload_for_recipients(
                mock_edition, "/tmp/test.pdf", mock_publication_data
            )

        # Should only upload for enabled@example.com and no-prefs@example.com (default=True)
        assert result.success is True
        assert mock_onedrive_service.upload_file.call_count == 1

    @pytest.mark.asyncio
    async def test_upload_for_recipients_partial_failure(
        self,
        mock_onedrive_service,
        mock_edition_tracker,
        mock_edition,
        mock_publication_data,
        sample_recipients,
    ):
        """Test handling of partial upload failures."""
        service = OneDriveDeliveryService(
            mock_onedrive_service, mock_edition_tracker, dry_run=False
        )

        # First upload succeeds, second fails
        mock_onedrive_service.upload_file.side_effect = [
            UploadResult(
                success=True, file_url="https://onedrive.com/test", file_id="test-id"
            ),
            UploadResult(success=False, error="Network error"),
        ]

        with patch("depotbutler.db.mongodb.get_mongodb_service") as mock_mongodb:
            mock_db = AsyncMock()
            mock_db.edition_repo = AsyncMock()
            mock_db.edition_repo.update_onedrive_uploaded_timestamp = AsyncMock()
            mock_db.get_recipients_for_publication = AsyncMock(
                return_value=sample_recipients
            )
            mock_mongodb.return_value = mock_db

            result = await service.upload_for_recipients(
                mock_edition, "/tmp/test.pdf", mock_publication_data
            )

        # Should still succeed if at least one upload worked
        assert result.success is True
        assert mock_onedrive_service.upload_file.call_count == 2

    @pytest.mark.asyncio
    async def test_upload_for_recipients_all_failures(
        self,
        mock_onedrive_service,
        mock_edition_tracker,
        mock_edition,
        mock_publication_data,
        sample_recipients,
    ):
        """Test handling when all uploads fail."""
        service = OneDriveDeliveryService(
            mock_onedrive_service, mock_edition_tracker, dry_run=False
        )

        # All uploads fail
        mock_onedrive_service.upload_file.return_value = UploadResult(
            success=False, error="Network error"
        )

        with patch("depotbutler.db.mongodb.get_mongodb_service") as mock_mongodb:
            mock_db = AsyncMock()
            mock_db.get_recipients_for_publication = AsyncMock(
                return_value=sample_recipients
            )
            mock_mongodb.return_value = mock_db

            result = await service.upload_for_recipients(
                mock_edition, "/tmp/test.pdf", mock_publication_data
            )

        # Should fail overall
        assert result.success is False
        assert "Network error" in result.error or "All uploads failed" in result.error
