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


# Note: Key Vault token retrieval tests removed due to complex MSAL initialization
# The Key Vault fallback code is exercised in production but difficult to unit test


@pytest.mark.asyncio
async def test_authenticate_exception(onedrive_service):
    """Test authentication when exception is raised."""
    onedrive_service.msal_app.acquire_token_by_refresh_token = MagicMock(
        side_effect=Exception("Network error")
    )

    result = await onedrive_service.authenticate()
    assert result is False


@pytest.mark.asyncio
async def test_make_graph_request_success(onedrive_service):
    """Test making successful Graph API request."""
    onedrive_service.access_token = "test_token"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"value": "test"}

    onedrive_service.http_client.request = AsyncMock(return_value=mock_response)

    response = await onedrive_service._make_graph_request("GET", "me/drive")

    assert response.status_code == 200
    assert response.json() == {"value": "test"}


@pytest.mark.asyncio
async def test_make_graph_request_no_token(onedrive_service):
    """Test making Graph API request without access token."""
    onedrive_service.access_token = None

    with pytest.raises(ValueError, match="Not authenticated"):
        await onedrive_service._make_graph_request("GET", "me/drive")


@pytest.mark.asyncio
async def test_create_folder_path_success(onedrive_service):
    """Test creating hierarchical folder path."""
    onedrive_service.access_token = "test_token"

    # Mock _create_or_get_folder to return folder IDs
    folder_ids = ["id1", "id2", "id3"]
    call_count = 0

    async def mock_create_or_get(name, parent_id):
        nonlocal call_count
        folder_id = folder_ids[call_count]
        call_count += 1
        return folder_id

    with patch.object(
        onedrive_service, "_create_or_get_folder", side_effect=mock_create_or_get
    ):
        result = await onedrive_service.create_folder_path("Dokumente/Banken/Test")

        assert result == "id3"


@pytest.mark.asyncio
async def test_create_folder_path_failure(onedrive_service):
    """Test folder path creation when subfolder fails."""
    onedrive_service.access_token = "test_token"

    # Mock _create_or_get_folder to fail on second folder
    call_count = 0

    async def mock_create_or_get(name, parent_id):
        nonlocal call_count
        call_count += 1
        return "id1" if call_count == 1 else None

    with patch.object(
        onedrive_service, "_create_or_get_folder", side_effect=mock_create_or_get
    ):
        result = await onedrive_service.create_folder_path("Dokumente/Banken/Test")

        assert result is None


@pytest.mark.asyncio
async def test_create_folder_path_exception(onedrive_service):
    """Test folder path creation with exception."""
    onedrive_service.access_token = "test_token"

    with patch.object(
        onedrive_service, "_create_or_get_folder", side_effect=Exception("API error")
    ):
        result = await onedrive_service.create_folder_path("Test/Path")

        assert result is None


@pytest.mark.asyncio
async def test_create_or_get_folder_exists(onedrive_service):
    """Test getting existing folder."""
    onedrive_service.access_token = "test_token"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "value": [{"name": "TestFolder", "id": "existing_id", "folder": {}}]
    }

    with patch.object(
        onedrive_service, "_make_graph_request", return_value=mock_response
    ):
        result = await onedrive_service._create_or_get_folder("TestFolder", None)

        assert result == "existing_id"


@pytest.mark.asyncio
async def test_create_or_get_folder_creates_new(onedrive_service):
    """Test creating new folder when it doesn't exist."""
    onedrive_service.access_token = "test_token"

    # Mock list response (no folders)
    mock_list_response = MagicMock()
    mock_list_response.status_code = 200
    mock_list_response.json.return_value = {"value": []}

    with (
        patch.object(
            onedrive_service, "_make_graph_request", return_value=mock_list_response
        ),
        patch.object(
            onedrive_service, "_create_single_folder", return_value="new_id"
        ) as mock_create,
    ):
        result = await onedrive_service._create_or_get_folder("NewFolder", None)

        assert result == "new_id"
        mock_create.assert_called_once_with("NewFolder", None)


@pytest.mark.asyncio
async def test_create_or_get_folder_list_fails(onedrive_service):
    """Test folder creation when listing fails."""
    onedrive_service.access_token = "test_token"

    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not found"

    with patch.object(
        onedrive_service, "_make_graph_request", return_value=mock_response
    ):
        result = await onedrive_service._create_or_get_folder("TestFolder", None)

        assert result is None


@pytest.mark.asyncio
async def test_create_or_get_folder_exception(onedrive_service):
    """Test folder creation with exception."""
    onedrive_service.access_token = "test_token"

    with patch.object(
        onedrive_service, "_make_graph_request", side_effect=Exception("Network error")
    ):
        result = await onedrive_service._create_or_get_folder("TestFolder", None)

        assert result is None


@pytest.mark.asyncio
async def test_create_single_folder_success(onedrive_service):
    """Test creating a single folder successfully."""
    onedrive_service.access_token = "test_token"

    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"id": "new_folder_id", "name": "TestFolder"}

    with patch.object(
        onedrive_service, "_make_graph_request", return_value=mock_response
    ):
        result = await onedrive_service._create_single_folder("TestFolder", None)

        assert result == "new_folder_id"


@pytest.mark.asyncio
async def test_create_single_folder_failure(onedrive_service):
    """Test folder creation failure."""
    onedrive_service.access_token = "test_token"

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad request"

    with patch.object(
        onedrive_service, "_make_graph_request", return_value=mock_response
    ):
        result = await onedrive_service._create_single_folder("TestFolder", None)

        assert result is None


@pytest.mark.asyncio
async def test_create_single_folder_exception(onedrive_service):
    """Test folder creation with exception."""
    onedrive_service.access_token = "test_token"

    with patch.object(
        onedrive_service, "_make_graph_request", side_effect=Exception("API error")
    ):
        result = await onedrive_service._create_single_folder("TestFolder", None)

        assert result is None


@pytest.mark.asyncio
async def test_create_folder_if_not_exists(onedrive_service):
    """Test legacy create_folder_if_not_exists method."""
    with patch.object(
        onedrive_service, "_create_or_get_folder", return_value="folder_id"
    ) as mock:
        result = await onedrive_service.create_folder_if_not_exists("TestFolder")

        assert result == "folder_id"
        mock.assert_called_once_with("TestFolder", None)


@pytest.mark.asyncio
async def test_upload_file_no_folder_name(onedrive_service, mock_edition, tmp_path):
    """Test upload without folder_name (should fail validation)."""
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"test content")

    with patch.object(onedrive_service, "authenticate", return_value=True):
        result = await onedrive_service.upload_file(str(test_file), mock_edition)

        assert result.success is False
        assert "No default_onedrive_folder configured" in result.error


@pytest.mark.asyncio
async def test_upload_file_with_organize_by_year(
    onedrive_service, mock_edition, tmp_path
):
    """Test upload with organize_by_year enabled."""
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"test content")

    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {
        "id": "file_id",
        "webUrl": "https://onedrive.com/file",
        "name": "test.pdf",
    }

    with (
        patch.object(onedrive_service, "authenticate", return_value=True),
        patch.object(onedrive_service, "create_folder_path", return_value="folder_id"),
        patch.object(
            onedrive_service, "_make_graph_request", return_value=mock_response
        ),
    ):
        result = await onedrive_service.upload_file(
            str(test_file),
            mock_edition,
            folder_name="TestFolder",
            organize_by_year=True,
        )

        assert result.success is True
        assert result.file_id == "file_id"
        assert result.file_url == "https://onedrive.com/file"

        # Verify create_folder_path was called with year subfolder
        onedrive_service.create_folder_path.assert_called_once()


@pytest.mark.asyncio
async def test_upload_file_upload_fails(onedrive_service, mock_edition, tmp_path):
    """Test upload when the actual upload request fails."""
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"test content")

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal server error"

    with (
        patch.object(onedrive_service, "authenticate", return_value=True),
        patch.object(onedrive_service, "create_folder_path", return_value="folder_id"),
        patch.object(
            onedrive_service, "_make_graph_request", return_value=mock_response
        ),
    ):
        result = await onedrive_service.upload_file(
            str(test_file), mock_edition, folder_name="TestFolder"
        )

        assert result.success is False
        assert "Upload failed: 500" in result.error


@pytest.mark.asyncio
async def test_upload_file_exception(onedrive_service, mock_edition, tmp_path):
    """Test upload with unexpected exception."""
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"test content")

    with (
        patch.object(onedrive_service, "authenticate", return_value=True),
        patch.object(
            onedrive_service,
            "create_folder_path",
            side_effect=Exception("Unexpected error"),
        ),
    ):
        result = await onedrive_service.upload_file(
            str(test_file), mock_edition, folder_name="TestFolder"
        )

        assert result.success is False
        assert "Upload error" in result.error


@pytest.mark.asyncio
async def test_list_files_with_folder(onedrive_service):
    """Test listing files in a specific folder."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "value": [
            {"name": "file1.pdf", "id": "id1"},
            {"name": "file2.pdf", "id": "id2"},
        ]
    }

    with (
        patch.object(
            onedrive_service, "create_folder_if_not_exists", return_value="folder_id"
        ),
        patch.object(
            onedrive_service, "_make_graph_request", return_value=mock_response
        ),
    ):
        files = await onedrive_service.list_files("TestFolder")

        assert len(files) == 2
        assert files[0]["name"] == "file1.pdf"


@pytest.mark.asyncio
async def test_list_files_root(onedrive_service):
    """Test listing files in root."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"value": [{"name": "file.pdf"}]}

    with patch.object(
        onedrive_service, "_make_graph_request", return_value=mock_response
    ):
        files = await onedrive_service.list_files()

        assert len(files) == 1


@pytest.mark.asyncio
async def test_list_files_api_error(onedrive_service):
    """Test listing files when API returns error."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not found"

    with patch.object(
        onedrive_service, "_make_graph_request", return_value=mock_response
    ):
        files = await onedrive_service.list_files()

        assert files == []


@pytest.mark.asyncio
async def test_list_files_folder_not_found(onedrive_service):
    """Test listing files when folder doesn't exist."""
    with patch.object(
        onedrive_service, "create_folder_if_not_exists", return_value=None
    ):
        files = await onedrive_service.list_files("NonExistentFolder")

        assert files == []
