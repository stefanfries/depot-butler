"""Tests for OneDrive multi-recipient upload functionality.

This test module covers:
- upload_for_recipients() method
- Multi-recipient upload scenarios
- Recipient folder customization
- Organize by year feature
- Error handling for individual recipient failures
- Batch upload result aggregation
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from depotbutler.models import Edition, UploadResult
from depotbutler.onedrive import OneDriveService


@pytest.fixture
def mock_settings():
    """Create mock settings for OneDriveService."""
    settings = MagicMock()
    settings.onedrive.client_id = "test_client_id"
    settings.onedrive.client_secret = MagicMock()
    settings.onedrive.client_secret.get_secret_value.return_value = "test_secret"
    settings.onedrive.refresh_token = MagicMock()
    settings.onedrive.refresh_token.get_secret_value.return_value = "test_refresh_token"
    settings.onedrive.folder_path = "test/folder"
    settings.onedrive.organize_by_year = False
    return settings


@pytest.fixture
def onedrive_service(mock_settings):
    """Create OneDriveService with mocked dependencies."""
    with patch("depotbutler.onedrive.service.Settings", return_value=mock_settings):
        service = OneDriveService()
        service.access_token = "test_access_token"  # Pre-authenticated
        return service


@pytest.fixture
def mock_edition():
    """Create mock Edition for testing."""
    return Edition(
        title="Test Edition 47/2025",
        publication_date="2025-11-23",
        details_url="https://example.com/details",
        download_url="https://example.com/download",
    )


@pytest.fixture
def mock_publication():
    """Create mock publication document."""
    return {
        "publication_id": "test-pub",
        "name": "Test Publication",
        "active": True,
    }


@pytest.fixture
def sample_recipients():
    """Sample recipients with different OneDrive preferences."""
    return [
        {
            "email": "user1@example.com",
            "active": True,
            "publication_preferences": {
                "test-pub": {
                    "email_enabled": False,
                    "onedrive_enabled": True,
                    "custom_onedrive_folder": "User1/Custom",
                    "organize_by_year": True,
                }
            },
        },
        {
            "email": "user2@example.com",
            "active": True,
            "publication_preferences": {
                "test-pub": {
                    "email_enabled": False,
                    "onedrive_enabled": True,
                    "custom_onedrive_folder": "User2/Folder",
                    "organize_by_year": False,
                }
            },
        },
        {
            "email": "user3@example.com",
            "active": True,
            "publication_preferences": {
                "test-pub": {
                    "email_enabled": False,
                    "onedrive_enabled": True,
                    # No custom folder - uses publication default
                }
            },
        },
    ]


# ============================================================================
# Test: Multi-Recipient Uploads
# ============================================================================


@pytest.mark.asyncio
async def test_upload_for_recipients_success_all(
    onedrive_service, mock_edition, mock_publication, sample_recipients, tmp_path
):
    """Test successful upload to all recipients."""
    # Create test file
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"test content")

    with (
        patch(
            "depotbutler.db.mongodb.get_recipients_for_publication",
            new_callable=AsyncMock,
        ) as mock_get_recipients,
        patch(
            "depotbutler.db.mongodb.get_onedrive_folder_for_recipient"
        ) as mock_get_folder,
        patch(
            "depotbutler.db.mongodb.get_organize_by_year_for_recipient"
        ) as mock_get_organize,
        patch.object(
            onedrive_service, "upload_file", new_callable=AsyncMock
        ) as mock_upload,
    ):
        # Setup mocks
        mock_get_recipients.return_value = sample_recipients
        mock_get_folder.side_effect = ["User1/Custom", "User2/Folder", "DefaultFolder"]
        mock_get_organize.side_effect = [True, False, True]

        # Mock successful uploads
        def create_success(recipient_idx):
            return UploadResult(
                success=True,
                file_id=f"file_{recipient_idx}",
                file_url=f"https://example.com/file_{recipient_idx}",
                filename="test.pdf",
            )

        mock_upload.side_effect = [create_success(i) for i in range(3)]

        # Execute
        results = await onedrive_service.upload_for_recipients(
            mock_edition, mock_publication, str(test_file)
        )

        # Verify
        assert len(results) == 3
        assert all(r.success for r in results)
        assert results[0].recipient_email == "user1@example.com"
        assert results[1].recipient_email == "user2@example.com"
        assert results[2].recipient_email == "user3@example.com"

        # Verify upload_file called with correct parameters for each recipient
        assert mock_upload.call_count == 3
        calls = mock_upload.call_args_list

        # User1: custom folder, organize by year
        assert calls[0][1]["folder_name"] == "User1/Custom"
        assert calls[0][1]["organize_by_year"] is True

        # User2: custom folder, no organize by year
        assert calls[1][1]["folder_name"] == "User2/Folder"
        assert calls[1][1]["organize_by_year"] is False

        # User3: default folder, organize by year
        assert calls[2][1]["folder_name"] == "DefaultFolder"
        assert calls[2][1]["organize_by_year"] is True


@pytest.mark.asyncio
async def test_upload_for_recipients_partial_failure(
    onedrive_service, mock_edition, mock_publication, sample_recipients, tmp_path
):
    """Test upload when some recipients fail."""
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"test content")

    with (
        patch(
            "depotbutler.db.mongodb.get_recipients_for_publication",
            new_callable=AsyncMock,
        ) as mock_get_recipients,
        patch(
            "depotbutler.db.mongodb.get_onedrive_folder_for_recipient"
        ) as mock_get_folder,
        patch(
            "depotbutler.db.mongodb.get_organize_by_year_for_recipient"
        ) as mock_get_organize,
        patch.object(
            onedrive_service, "upload_file", new_callable=AsyncMock
        ) as mock_upload,
    ):
        mock_get_recipients.return_value = sample_recipients
        mock_get_folder.return_value = "TestFolder"
        mock_get_organize.return_value = False

        # Mock mixed results: success, failure, success
        mock_upload.side_effect = [
            UploadResult(success=True, file_id="file1", filename="test.pdf"),
            UploadResult(success=False, error="Network timeout"),
            UploadResult(success=True, file_id="file3", filename="test.pdf"),
        ]

        # Execute
        results = await onedrive_service.upload_for_recipients(
            mock_edition, mock_publication, str(test_file)
        )

        # Verify
        assert len(results) == 3
        assert results[0].success is True
        assert results[1].success is False
        assert results[2].success is True
        assert results[1].error == "Network timeout"

        # All recipients should be attempted even if one fails
        assert mock_upload.call_count == 3


@pytest.mark.asyncio
async def test_upload_for_recipients_exception_handling(
    onedrive_service, mock_edition, mock_publication, sample_recipients, tmp_path
):
    """Test that exceptions during individual uploads are caught and recorded."""
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"test content")

    with (
        patch(
            "depotbutler.db.mongodb.get_recipients_for_publication",
            new_callable=AsyncMock,
        ) as mock_get_recipients,
        patch(
            "depotbutler.db.mongodb.get_onedrive_folder_for_recipient"
        ) as mock_get_folder,
        patch(
            "depotbutler.db.mongodb.get_organize_by_year_for_recipient"
        ) as mock_get_organize,
        patch.object(
            onedrive_service, "upload_file", new_callable=AsyncMock
        ) as mock_upload,
    ):
        mock_get_recipients.return_value = sample_recipients[:2]  # Only 2 recipients
        mock_get_folder.side_effect = ["Folder1", Exception("Folder resolution failed")]
        mock_get_organize.return_value = False

        mock_upload.return_value = UploadResult(
            success=True, file_id="file1", filename="test.pdf"
        )

        # Execute
        results = await onedrive_service.upload_for_recipients(
            mock_edition, mock_publication, str(test_file)
        )

        # Verify
        assert len(results) == 2
        assert results[0].success is True
        assert results[1].success is False
        assert "Folder resolution failed" in results[1].error
        assert results[1].recipient_email == "user2@example.com"


@pytest.mark.asyncio
async def test_upload_for_recipients_no_recipients(
    onedrive_service, mock_edition, mock_publication, tmp_path
):
    """Test upload when no recipients are enabled for the publication."""
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"test content")

    with patch(
        "depotbutler.db.mongodb.get_recipients_for_publication",
        new_callable=AsyncMock,
    ) as mock_get_recipients:
        mock_get_recipients.return_value = []

        # Execute
        results = await onedrive_service.upload_for_recipients(
            mock_edition, mock_publication, str(test_file)
        )

        # Verify
        assert results == []


# ============================================================================
# Test: Custom Folder Paths
# ============================================================================


@pytest.mark.asyncio
async def test_upload_for_recipients_custom_folders(
    onedrive_service, mock_edition, mock_publication, tmp_path
):
    """Test that custom folder paths are correctly resolved per recipient."""
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"test content")

    recipients = [
        {
            "email": "user1@example.com",
            "publication_preferences": {
                "test-pub": {
                    "onedrive_enabled": True,
                    "custom_onedrive_folder": "Custom/Path/A",
                }
            },
        },
        {
            "email": "user2@example.com",
            "publication_preferences": {
                "test-pub": {
                    "onedrive_enabled": True,
                    "custom_onedrive_folder": "Custom/Path/B",
                }
            },
        },
    ]

    with (
        patch(
            "depotbutler.db.mongodb.get_recipients_for_publication",
            new_callable=AsyncMock,
        ) as mock_get_recipients,
        patch(
            "depotbutler.db.mongodb.get_onedrive_folder_for_recipient"
        ) as mock_get_folder,
        patch(
            "depotbutler.db.mongodb.get_organize_by_year_for_recipient"
        ) as mock_get_organize,
        patch.object(
            onedrive_service, "upload_file", new_callable=AsyncMock
        ) as mock_upload,
    ):
        mock_get_recipients.return_value = recipients
        mock_get_folder.side_effect = ["Custom/Path/A", "Custom/Path/B"]
        mock_get_organize.return_value = False

        mock_upload.return_value = UploadResult(
            success=True, file_id="file1", filename="test.pdf"
        )

        # Execute
        await onedrive_service.upload_for_recipients(
            mock_edition, mock_publication, str(test_file)
        )

        # Verify both custom folders used
        assert mock_upload.call_count == 2
        assert mock_upload.call_args_list[0][1]["folder_name"] == "Custom/Path/A"
        assert mock_upload.call_args_list[1][1]["folder_name"] == "Custom/Path/B"


# ============================================================================
# Test: Organize by Year Feature
# ============================================================================


@pytest.mark.asyncio
async def test_upload_for_recipients_organize_by_year_mixed(
    onedrive_service, mock_edition, mock_publication, tmp_path
):
    """Test that organize_by_year is correctly resolved per recipient."""
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"test content")

    recipients = [
        {
            "email": "user1@example.com",
            "publication_preferences": {
                "test-pub": {
                    "onedrive_enabled": True,
                    "organize_by_year": True,
                }
            },
        },
        {
            "email": "user2@example.com",
            "publication_preferences": {
                "test-pub": {
                    "onedrive_enabled": True,
                    "organize_by_year": False,
                }
            },
        },
        {
            "email": "user3@example.com",
            "publication_preferences": {
                "test-pub": {
                    "onedrive_enabled": True,
                    # No organize_by_year - uses publication default
                }
            },
        },
    ]

    with (
        patch(
            "depotbutler.db.mongodb.get_recipients_for_publication",
            new_callable=AsyncMock,
        ) as mock_get_recipients,
        patch(
            "depotbutler.db.mongodb.get_onedrive_folder_for_recipient"
        ) as mock_get_folder,
        patch(
            "depotbutler.db.mongodb.get_organize_by_year_for_recipient"
        ) as mock_get_organize,
        patch.object(
            onedrive_service, "upload_file", new_callable=AsyncMock
        ) as mock_upload,
    ):
        mock_get_recipients.return_value = recipients
        mock_get_folder.return_value = "TestFolder"
        mock_get_organize.side_effect = [True, False, True]  # Mixed values

        mock_upload.return_value = UploadResult(
            success=True, file_id="file1", filename="test.pdf"
        )

        # Execute
        await onedrive_service.upload_for_recipients(
            mock_edition, mock_publication, str(test_file)
        )

        # Verify organize_by_year correctly passed per recipient
        assert mock_upload.call_count == 3
        assert mock_upload.call_args_list[0][1]["organize_by_year"] is True
        assert mock_upload.call_args_list[1][1]["organize_by_year"] is False
        assert mock_upload.call_args_list[2][1]["organize_by_year"] is True


# ============================================================================
# Test: Error Scenarios
# ============================================================================


@pytest.mark.asyncio
async def test_upload_for_recipients_get_recipients_fails(
    onedrive_service, mock_edition, mock_publication, tmp_path
):
    """Test handling when getting recipients fails."""
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"test content")

    with patch(
        "depotbutler.db.mongodb.get_recipients_for_publication",
        new_callable=AsyncMock,
    ) as mock_get_recipients:
        mock_get_recipients.side_effect = Exception("Database connection failed")

        # Execute
        results = await onedrive_service.upload_for_recipients(
            mock_edition, mock_publication, str(test_file)
        )

        # Verify returns empty list on exception
        assert results == []


@pytest.mark.asyncio
async def test_upload_for_recipients_all_fail(
    onedrive_service, mock_edition, mock_publication, sample_recipients, tmp_path
):
    """Test upload when all recipients fail."""
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"test content")

    with (
        patch(
            "depotbutler.db.mongodb.get_recipients_for_publication",
            new_callable=AsyncMock,
        ) as mock_get_recipients,
        patch(
            "depotbutler.db.mongodb.get_onedrive_folder_for_recipient"
        ) as mock_get_folder,
        patch(
            "depotbutler.db.mongodb.get_organize_by_year_for_recipient"
        ) as mock_get_organize,
        patch.object(
            onedrive_service, "upload_file", new_callable=AsyncMock
        ) as mock_upload,
    ):
        mock_get_recipients.return_value = sample_recipients
        mock_get_folder.return_value = "TestFolder"
        mock_get_organize.return_value = False

        # All uploads fail
        mock_upload.return_value = UploadResult(
            success=False, error="OneDrive quota exceeded"
        )

        # Execute
        results = await onedrive_service.upload_for_recipients(
            mock_edition, mock_publication, str(test_file)
        )

        # Verify all failed
        assert len(results) == 3
        assert all(not r.success for r in results)
        assert all("OneDrive quota exceeded" in r.error for r in results)


# ============================================================================
# Test: Result Aggregation
# ============================================================================


@pytest.mark.asyncio
async def test_upload_for_recipients_result_has_recipient_email(
    onedrive_service, mock_edition, mock_publication, tmp_path
):
    """Test that each result includes recipient email for tracking."""
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"test content")

    recipients = [
        {
            "email": "alice@example.com",
            "publication_preferences": {"test-pub": {"onedrive_enabled": True}},
        },
        {
            "email": "bob@example.com",
            "publication_preferences": {"test-pub": {"onedrive_enabled": True}},
        },
    ]

    with (
        patch(
            "depotbutler.db.mongodb.get_recipients_for_publication",
            new_callable=AsyncMock,
        ) as mock_get_recipients,
        patch(
            "depotbutler.db.mongodb.get_onedrive_folder_for_recipient"
        ) as mock_get_folder,
        patch(
            "depotbutler.db.mongodb.get_organize_by_year_for_recipient"
        ) as mock_get_organize,
        patch.object(
            onedrive_service, "upload_file", new_callable=AsyncMock
        ) as mock_upload,
    ):
        mock_get_recipients.return_value = recipients
        mock_get_folder.return_value = "TestFolder"
        mock_get_organize.return_value = False

        # Mock needs to return different objects each time
        mock_upload.side_effect = [
            UploadResult(success=True, file_id="file1", filename="test.pdf"),
            UploadResult(success=True, file_id="file2", filename="test.pdf"),
        ]

        # Execute
        results = await onedrive_service.upload_for_recipients(
            mock_edition, mock_publication, str(test_file)
        )

        # Verify recipient_email populated
        assert len(results) == 2
        assert results[0].recipient_email == "alice@example.com"
        assert results[1].recipient_email == "bob@example.com"


@pytest.mark.asyncio
async def test_upload_for_recipients_single_recipient(
    onedrive_service, mock_edition, mock_publication, tmp_path
):
    """Test upload with single recipient."""
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"test content")

    recipients = [
        {
            "email": "only@example.com",
            "publication_preferences": {
                "test-pub": {
                    "onedrive_enabled": True,
                    "custom_onedrive_folder": "MySingleFolder",
                }
            },
        }
    ]

    with (
        patch(
            "depotbutler.db.mongodb.get_recipients_for_publication",
            new_callable=AsyncMock,
        ) as mock_get_recipients,
        patch(
            "depotbutler.db.mongodb.get_onedrive_folder_for_recipient"
        ) as mock_get_folder,
        patch(
            "depotbutler.db.mongodb.get_organize_by_year_for_recipient"
        ) as mock_get_organize,
        patch.object(
            onedrive_service, "upload_file", new_callable=AsyncMock
        ) as mock_upload,
    ):
        mock_get_recipients.return_value = recipients
        mock_get_folder.return_value = "MySingleFolder"
        mock_get_organize.return_value = True

        mock_upload.return_value = UploadResult(
            success=True, file_id="file1", filename="test.pdf"
        )

        # Execute
        results = await onedrive_service.upload_for_recipients(
            mock_edition, mock_publication, str(test_file)
        )

        # Verify
        assert len(results) == 1
        assert results[0].success is True
        assert results[0].recipient_email == "only@example.com"
        assert mock_upload.call_args[1]["folder_name"] == "MySingleFolder"
        assert mock_upload.call_args[1]["organize_by_year"] is True
