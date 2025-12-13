"""Tests for OneDrive service (onedrive.py)."""

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
    settings.onedrive.base_folder_path = "/Dokumente/Test"
    settings.onedrive.organize_by_year = False
    return settings


@pytest.fixture
def onedrive_service(mock_settings):
    """Create OneDriveService with mocked dependencies."""
    with patch("depotbutler.onedrive.Settings", return_value=mock_settings):
        service = OneDriveService()
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


def test_onedrive_service_initialization(onedrive_service):
    """Test OneDriveService initialization."""
    assert onedrive_service.client_id == "test_client_id"
    assert onedrive_service.client_secret == "test_secret"
    assert onedrive_service.refresh_token == "test_refresh_token"
    assert onedrive_service.access_token is None
    assert onedrive_service.graph_url == "https://graph.microsoft.com/v1.0"


def test_get_refresh_token_from_environment(mock_settings):
    """Test retrieving refresh token from environment variable."""
    with patch("depotbutler.onedrive.Settings", return_value=mock_settings):
        service = OneDriveService()
        assert service.refresh_token == "test_refresh_token"


@pytest.mark.asyncio
async def test_authenticate_success(onedrive_service):
    """Test successful authentication with refresh token."""
    mock_result = {"access_token": "new_access_token"}

    onedrive_service.msal_app.acquire_token_by_refresh_token = MagicMock(
        return_value=mock_result
    )

    result = await onedrive_service.authenticate()

    assert result is True
    assert onedrive_service.access_token == "new_access_token"


@pytest.mark.asyncio
async def test_authenticate_failure(onedrive_service):
    """Test authentication failure."""
    mock_result = {"error": "invalid_grant", "error_description": "Token expired"}

    onedrive_service.msal_app.acquire_token_by_refresh_token = MagicMock(
        return_value=mock_result
    )

    result = await onedrive_service.authenticate()

    assert result is False
    assert onedrive_service.access_token is None


@pytest.mark.asyncio
async def test_authenticate_no_refresh_token(mock_settings):
    """Test authentication without refresh token."""
    mock_settings.onedrive.refresh_token.get_secret_value.return_value = None

    with patch("depotbutler.onedrive.Settings", return_value=mock_settings):
        service = OneDriveService()
        result = await service.authenticate()

        assert result is False


@pytest.mark.asyncio
async def test_upload_file_authentication_failure(
    onedrive_service, mock_edition, tmp_path
):
    """Test upload when authentication fails."""
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"test content")

    # Mock authentication failure
    with patch.object(onedrive_service, "authenticate", return_value=False):
        result = await onedrive_service.upload_file(str(test_file), mock_edition)

        assert isinstance(result, UploadResult)
        assert result.success is False
        assert result.error is not None
        assert "Authentication failed" in result.error


@pytest.mark.asyncio
async def test_upload_file_not_found(onedrive_service, mock_edition):
    """Test upload with non-existent file."""
    # Mock authentication to succeed
    with patch.object(onedrive_service, "authenticate", return_value=True):
        with patch.object(
            onedrive_service, "create_folder_path", return_value="folder123"
        ):
            result = await onedrive_service.upload_file(
                "/nonexistent/file.pdf", mock_edition, folder_name="TestFolder"
            )

            assert isinstance(result, UploadResult)
            assert result.success is False
            assert result.error is not None
            assert "not found" in result.error.lower()


@pytest.mark.asyncio
async def test_upload_file_folder_creation_fails(
    onedrive_service, mock_edition, tmp_path
):
    """Test upload when folder creation fails."""
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"test content")

    with patch.object(onedrive_service, "authenticate", return_value=True):
        with patch.object(onedrive_service, "create_folder_path", return_value=None):
            result = await onedrive_service.upload_file(
                str(test_file), mock_edition, folder_name="TestFolder"
            )

            assert isinstance(result, UploadResult)
            assert result.success is False
            assert result.error is not None
            assert "Failed to create folder path" in result.error


@pytest.mark.asyncio
async def test_close(onedrive_service):
    """Test closing HTTP client."""
    mock_close = AsyncMock()
    onedrive_service.http_client.aclose = mock_close

    await onedrive_service.close()

    mock_close.assert_called_once()


@pytest.mark.asyncio
async def test_list_files_error(onedrive_service):
    """Test listing files when API returns error."""
    # Test that an exception in the code path returns empty list
    with patch.object(
        onedrive_service, "authenticate", side_effect=Exception("Test error")
    ):
        files = await onedrive_service.list_files()
        assert files == []
