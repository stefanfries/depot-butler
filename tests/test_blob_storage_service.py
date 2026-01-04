"""Unit tests for BlobStorageService."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from depotbutler.exceptions import ConfigurationError, UploadError
from depotbutler.services.blob_storage_service import BlobStorageService


@pytest.fixture
def mock_blob_service_client():
    """Mock Azure BlobServiceClient."""
    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_container.exists.return_value = True
    mock_client.get_container_client.return_value = mock_container
    return mock_client


@pytest.fixture
def mock_settings():
    """Mock settings with blob storage configuration."""
    settings = MagicMock()
    settings.blob_storage.connection_string.get_secret_value.return_value = (
        "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test123=="
    )
    settings.blob_storage.container_name = "test-editions"
    settings.blob_storage.enabled = True
    return settings


class TestBlobStorageServiceInitialization:
    """Test BlobStorageService initialization."""

    def test_initialization_success(self, mock_settings):
        """Test successful initialization with valid connection string."""
        with patch(
            "depotbutler.services.blob_storage_service.BlobServiceClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_container = MagicMock()
            mock_container.exists.return_value = True
            mock_client.get_container_client.return_value = mock_container
            mock_client_class.from_connection_string.return_value = mock_client

            with patch(
                "depotbutler.services.blob_storage_service.settings", mock_settings
            ):
                service = BlobStorageService()

                assert service.container_name == "test-editions"
                assert service.connection_string is not None
                mock_client_class.from_connection_string.assert_called_once()

    def test_initialization_no_connection_string(self):
        """Test initialization fails when connection string is None."""
        mock_settings = MagicMock()
        mock_settings.blob_storage.connection_string = None

        with (
            patch("depotbutler.services.blob_storage_service.settings", mock_settings),
            pytest.raises(ConfigurationError, match="connection string not configured"),
        ):
            BlobStorageService()

    def test_initialization_empty_connection_string(self):
        """Test initialization fails when connection string is empty."""
        mock_settings = MagicMock()
        mock_settings.blob_storage.connection_string.get_secret_value.return_value = ""

        with (
            patch("depotbutler.services.blob_storage_service.settings", mock_settings),
            pytest.raises(ConfigurationError, match="connection string is empty"),
        ):
            BlobStorageService()

    def test_initialization_creates_container_if_missing(self, mock_settings):
        """Test container is created if it doesn't exist."""
        with patch(
            "depotbutler.services.blob_storage_service.BlobServiceClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_container = MagicMock()
            mock_container.exists.return_value = False  # Container doesn't exist
            mock_client.get_container_client.return_value = mock_container
            mock_client_class.from_connection_string.return_value = mock_client

            with patch(
                "depotbutler.services.blob_storage_service.settings", mock_settings
            ):
                BlobStorageService()

                mock_container.create_container.assert_called_once()

    def test_custom_container_name(self, mock_settings):
        """Test initialization with custom container name."""
        with patch(
            "depotbutler.services.blob_storage_service.BlobServiceClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_container = MagicMock()
            mock_container.exists.return_value = True
            mock_client.get_container_client.return_value = mock_container
            mock_client_class.from_connection_string.return_value = mock_client

            with patch(
                "depotbutler.services.blob_storage_service.settings", mock_settings
            ):
                service = BlobStorageService(container_name="custom-container")

                assert service.container_name == "custom-container"


class TestBlobPathGeneration:
    """Test blob path generation logic."""

    def test_generate_blob_path_standard(self, mock_settings):
        """Test standard blob path generation."""
        with patch(
            "depotbutler.services.blob_storage_service.BlobServiceClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_container = MagicMock()
            mock_container.exists.return_value = True
            mock_client.get_container_client.return_value = mock_container
            mock_client_class.from_connection_string.return_value = mock_client

            with patch(
                "depotbutler.services.blob_storage_service.settings", mock_settings
            ):
                service = BlobStorageService()

                path = service._generate_blob_path(
                    publication_id="megatrend-folger",
                    date="2025-12-27",
                    filename="2025-12-27_Megatrend-Folger_51-2025.pdf",
                )

                assert (
                    path
                    == "megatrend-folger/2025/2025-12-27_Megatrend-Folger_51-2025.pdf"
                )

    def test_generate_blob_path_different_year(self, mock_settings):
        """Test blob path generation with different year."""
        with patch(
            "depotbutler.services.blob_storage_service.BlobServiceClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_container = MagicMock()
            mock_container.exists.return_value = True
            mock_client.get_container_client.return_value = mock_container
            mock_client_class.from_connection_string.return_value = mock_client

            with patch(
                "depotbutler.services.blob_storage_service.settings", mock_settings
            ):
                service = BlobStorageService()

                path = service._generate_blob_path(
                    publication_id="test-pub",
                    date="2024-01-15",
                    filename="test.pdf",
                )

                assert path == "test-pub/2024/test.pdf"


class TestArchiveEdition:
    """Test archive_edition method."""

    @pytest.mark.asyncio
    async def test_archive_edition_success(self, mock_settings):
        """Test successful edition archival."""
        with patch(
            "depotbutler.services.blob_storage_service.BlobServiceClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_container = MagicMock()
            mock_blob_client = MagicMock()

            mock_container.exists.return_value = True
            mock_client.get_container_client.return_value = mock_container
            mock_container.get_blob_client.return_value = mock_blob_client
            mock_client_class.from_connection_string.return_value = mock_client

            with patch(
                "depotbutler.services.blob_storage_service.settings", mock_settings
            ):
                service = BlobStorageService()

                result = await service.archive_edition(
                    pdf_bytes=b"%PDF-1.4\nTest PDF",
                    publication_id="test-pub",
                    date="2025-12-27",
                    filename="test.pdf",
                    metadata={"issue": "01/2025"},
                )

                # Blob service returns dict with metadata, not success boolean
                assert "blob_url" in result
                assert "blob_path" in result
                assert result["blob_path"] == "test-pub/2025/test.pdf"
                assert result["file_size_bytes"] == str(len(b"%PDF-1.4\nTest PDF"))
                assert "archived_at" in result
                mock_blob_client.upload_blob.assert_called_once()

    @pytest.mark.asyncio
    async def test_archive_edition_upload_error(self, mock_settings):
        """Test archive_edition handles upload errors."""
        with patch(
            "depotbutler.services.blob_storage_service.BlobServiceClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_container = MagicMock()
            mock_blob_client = MagicMock()

            mock_container.exists.return_value = True
            mock_client.get_container_client.return_value = mock_container
            mock_container.get_blob_client.return_value = mock_blob_client
            mock_blob_client.upload_blob.side_effect = Exception("Upload failed")
            mock_client_class.from_connection_string.return_value = mock_client

            with patch(
                "depotbutler.services.blob_storage_service.settings", mock_settings
            ):
                service = BlobStorageService()

                with pytest.raises(UploadError, match="Blob storage upload failed"):
                    await service.archive_edition(
                        pdf_bytes=b"%PDF-1.4\nTest PDF",
                        publication_id="test-pub",
                        date="2025-12-27",
                        filename="test.pdf",
                    )


class TestBlobStorageExists:
    """Test exists method."""

    @pytest.mark.asyncio
    async def test_exists_true(self, mock_settings):
        """Test exists returns True when blob exists."""
        with patch(
            "depotbutler.services.blob_storage_service.BlobServiceClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_container = MagicMock()
            mock_blob_client = MagicMock()

            mock_container.exists.return_value = True
            mock_client.get_container_client.return_value = mock_container
            mock_container.get_blob_client.return_value = mock_blob_client
            mock_blob_client.exists.return_value = True
            mock_client_class.from_connection_string.return_value = mock_client

            with patch(
                "depotbutler.services.blob_storage_service.settings", mock_settings
            ):
                service = BlobStorageService()

                result = await service.exists(
                    publication_id="test-pub",
                    date="2025-12-27",
                    filename="test.pdf",
                )

                assert result is True
                mock_blob_client.exists.assert_called_once()

    @pytest.mark.asyncio
    async def test_exists_false(self, mock_settings):
        """Test exists returns False when blob doesn't exist."""
        with patch(
            "depotbutler.services.blob_storage_service.BlobServiceClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_container = MagicMock()
            mock_blob_client = MagicMock()

            mock_container.exists.return_value = True
            mock_client.get_container_client.return_value = mock_container
            mock_container.get_blob_client.return_value = mock_blob_client
            mock_blob_client.exists.return_value = False
            mock_client_class.from_connection_string.return_value = mock_client

            with patch(
                "depotbutler.services.blob_storage_service.settings", mock_settings
            ):
                service = BlobStorageService()

                result = await service.exists(
                    publication_id="test-pub",
                    date="2025-12-27",
                    filename="test.pdf",
                )

                assert result is False


class TestCacheRetrieval:
    """Test get_cached_edition method - Priority 1."""

    @pytest.mark.asyncio
    async def test_get_cached_edition_success(self, mock_settings):
        """Test successful cache retrieval."""
        with patch(
            "depotbutler.services.blob_storage_service.BlobServiceClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_container = MagicMock()
            mock_blob_client = MagicMock()
            mock_download_stream = MagicMock()

            # Mock blob exists and download
            mock_container.exists.return_value = True
            mock_client.get_container_client.return_value = mock_container
            mock_container.get_blob_client.return_value = mock_blob_client
            mock_blob_client.exists.return_value = True
            test_pdf_bytes = b"%PDF-1.4\nTest PDF Content"
            mock_download_stream.readall.return_value = test_pdf_bytes
            mock_blob_client.download_blob.return_value = mock_download_stream
            mock_client_class.from_connection_string.return_value = mock_client

            with patch(
                "depotbutler.services.blob_storage_service.settings", mock_settings
            ):
                service = BlobStorageService()

                result = await service.get_cached_edition(
                    publication_id="megatrend-folger",
                    date="2025-12-27",
                    filename="2025-12-27_Megatrend-Folger_51-2025.pdf",
                )

                assert result == test_pdf_bytes
                mock_blob_client.exists.assert_called_once()
                mock_blob_client.download_blob.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cached_edition_not_found(self, mock_settings):
        """Test cache miss (edition not in cache)."""
        with patch(
            "depotbutler.services.blob_storage_service.BlobServiceClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_container = MagicMock()
            mock_blob_client = MagicMock()

            mock_container.exists.return_value = True
            mock_client.get_container_client.return_value = mock_container
            mock_container.get_blob_client.return_value = mock_blob_client
            mock_blob_client.exists.return_value = False  # Not in cache
            mock_client_class.from_connection_string.return_value = mock_client

            with patch(
                "depotbutler.services.blob_storage_service.settings", mock_settings
            ):
                service = BlobStorageService()

                result = await service.get_cached_edition(
                    publication_id="test-pub",
                    date="2025-12-27",
                    filename="test.pdf",
                )

                assert result is None
                mock_blob_client.exists.assert_called_once()
                mock_blob_client.download_blob.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_cached_edition_resource_not_found(self, mock_settings):
        """Test cache retrieval with ResourceNotFoundError."""
        from azure.core.exceptions import ResourceNotFoundError

        with patch(
            "depotbutler.services.blob_storage_service.BlobServiceClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_container = MagicMock()
            mock_blob_client = MagicMock()

            mock_container.exists.return_value = True
            mock_client.get_container_client.return_value = mock_container
            mock_container.get_blob_client.return_value = mock_blob_client
            mock_blob_client.exists.return_value = True
            # Simulate race condition: exists() returns True but download fails
            mock_blob_client.download_blob.side_effect = ResourceNotFoundError(
                "Blob not found"
            )
            mock_client_class.from_connection_string.return_value = mock_client

            with patch(
                "depotbutler.services.blob_storage_service.settings", mock_settings
            ):
                service = BlobStorageService()

                result = await service.get_cached_edition(
                    publication_id="test-pub",
                    date="2025-12-27",
                    filename="test.pdf",
                )

                assert result is None

    @pytest.mark.asyncio
    async def test_get_cached_edition_download_error(self, mock_settings):
        """Test cache retrieval with network failure."""
        from depotbutler.exceptions import TransientError

        with patch(
            "depotbutler.services.blob_storage_service.BlobServiceClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_container = MagicMock()
            mock_blob_client = MagicMock()

            mock_container.exists.return_value = True
            mock_client.get_container_client.return_value = mock_container
            mock_container.get_blob_client.return_value = mock_blob_client
            mock_blob_client.exists.return_value = True
            # Simulate network error during download
            mock_blob_client.download_blob.side_effect = Exception("Network timeout")
            mock_client_class.from_connection_string.return_value = mock_client

            with patch(
                "depotbutler.services.blob_storage_service.settings", mock_settings
            ):
                service = BlobStorageService()

                with pytest.raises(
                    TransientError, match="Blob storage download failed"
                ):
                    await service.get_cached_edition(
                        publication_id="test-pub",
                        date="2025-12-27",
                        filename="test.pdf",
                    )


class TestListEditions:
    """Test list_editions method - Priority 1."""

    @pytest.mark.asyncio
    async def test_list_editions_by_publication(self, mock_settings):
        """Test listing editions filtered by publication."""
        with patch(
            "depotbutler.services.blob_storage_service.BlobServiceClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_container = MagicMock()

            # Create mock blobs
            mock_blob1 = MagicMock()
            mock_blob1.name = "megatrend-folger/2025/2025-12-27_Megatrend-Folger_51.pdf"
            mock_blob1.size = 1024
            mock_blob1.creation_time = datetime(2025, 12, 27, 10, 0, 0)
            mock_blob1.last_modified = datetime(2025, 12, 27, 10, 0, 0)

            mock_blob2 = MagicMock()
            mock_blob2.name = "megatrend-folger/2025/2025-12-20_Megatrend-Folger_50.pdf"
            mock_blob2.size = 95000
            mock_blob2.creation_time = datetime(2025, 12, 20, 15, 0, 0)
            mock_blob2.last_modified = datetime(2025, 12, 20, 15, 0, 0)

            mock_container.exists.return_value = True
            mock_client.get_container_client.return_value = mock_container
            mock_container.list_blobs.return_value = [mock_blob1, mock_blob2]
            mock_client_class.from_connection_string.return_value = mock_client

            with patch(
                "depotbutler.services.blob_storage_service.settings", mock_settings
            ):
                service = BlobStorageService()

                results = await service.list_editions(publication_id="megatrend-folger")

                assert len(results) == 2
                assert results[0]["blob_name"] == mock_blob1.name
                assert results[0]["size"] == "1024"
                assert results[1]["blob_name"] == mock_blob2.name

    @pytest.mark.asyncio
    async def test_list_editions_by_year(self, mock_settings):
        """Test listing editions filtered by year."""
        with patch(
            "depotbutler.services.blob_storage_service.BlobServiceClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_container = MagicMock()

            mock_blob = MagicMock()
            mock_blob.name = "2024/test-pub/2024-01-15_Test_01.pdf"
            mock_blob.size = 50000
            mock_blob.creation_time = datetime(2024, 1, 15, 12, 0, 0)
            mock_blob.last_modified = datetime(2024, 1, 15, 12, 0, 0)

            mock_container.exists.return_value = True
            mock_client.get_container_client.return_value = mock_container
            mock_container.list_blobs.return_value = [mock_blob]
            mock_container.url = "https://test.blob.core.windows.net/editions"
            mock_client_class.from_connection_string.return_value = mock_client

            with patch(
                "depotbutler.services.blob_storage_service.settings", mock_settings
            ):
                service = BlobStorageService()

                results = await service.list_editions(year="2024")

                assert len(results) == 1
                assert results[0]["blob_name"] == mock_blob.name
                assert "2024" in results[0]["blob_name"]
                mock_container.list_blobs.assert_called_once_with(
                    name_starts_with="2024/"
                )

    @pytest.mark.asyncio
    async def test_list_editions_by_year_and_publication(self, mock_settings):
        """Test listing editions filtered by both year and publication."""
        with patch(
            "depotbutler.services.blob_storage_service.BlobServiceClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_container = MagicMock()

            mock_blob = MagicMock()
            mock_blob.name = "megatrend-folger/2025/2025-12-27_Megatrend-Folger_51.pdf"
            mock_blob.size = 100000
            mock_blob.creation_time = datetime(2025, 12, 27, 15, 0, 0)
            mock_blob.last_modified = datetime(2025, 12, 27, 15, 0, 0)

            mock_container.exists.return_value = True
            mock_client.get_container_client.return_value = mock_container
            mock_container.list_blobs.return_value = [mock_blob]
            mock_container.url = "https://test.blob.core.windows.net/editions"
            mock_client_class.from_connection_string.return_value = mock_client

            with patch(
                "depotbutler.services.blob_storage_service.settings", mock_settings
            ):
                service = BlobStorageService()

                results = await service.list_editions(
                    publication_id="megatrend-folger", year="2025"
                )

                assert len(results) == 1
                assert results[0]["blob_name"] == mock_blob.name
                mock_container.list_blobs.assert_called_once_with(
                    name_starts_with="megatrend-folger/2025/"
                )

    @pytest.mark.asyncio
    async def test_list_editions_empty(self, mock_settings):
        """Test listing editions with no results."""
        with patch(
            "depotbutler.services.blob_storage_service.BlobServiceClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_container = MagicMock()

            mock_container.exists.return_value = True
            mock_client.get_container_client.return_value = mock_container
            mock_container.list_blobs.return_value = []  # No blobs
            mock_client_class.from_connection_string.return_value = mock_client

            with patch(
                "depotbutler.services.blob_storage_service.settings", mock_settings
            ):
                service = BlobStorageService()

                results = await service.list_editions(publication_id="nonexistent")

                assert len(results) == 0
                assert results == []

    @pytest.mark.asyncio
    async def test_list_editions_error_handling(self, mock_settings):
        """Test list_editions handles errors gracefully."""
        with patch(
            "depotbutler.services.blob_storage_service.BlobServiceClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_container = MagicMock()

            mock_container.exists.return_value = True
            mock_client.get_container_client.return_value = mock_container
            mock_container.list_blobs.side_effect = Exception("Network error")
            mock_client_class.from_connection_string.return_value = mock_client

            with patch(
                "depotbutler.services.blob_storage_service.settings", mock_settings
            ):
                service = BlobStorageService()

                results = await service.list_editions()

                # Should return empty list on error, not raise
                assert results == []


class TestFileOperations:
    """Test file-based operations - Priority 1."""

    @pytest.mark.asyncio
    async def test_download_to_file_success(self, mock_settings, tmp_path):
        """Test successful download to local file."""
        with patch(
            "depotbutler.services.blob_storage_service.BlobServiceClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_container = MagicMock()
            mock_blob_client = MagicMock()
            mock_download_stream = MagicMock()

            mock_container.exists.return_value = True
            mock_client.get_container_client.return_value = mock_container
            mock_container.get_blob_client.return_value = mock_blob_client
            mock_blob_client.exists.return_value = True
            test_pdf_bytes = b"%PDF-1.4\nTest PDF Content"
            mock_download_stream.readall.return_value = test_pdf_bytes
            mock_blob_client.download_blob.return_value = mock_download_stream
            mock_client_class.from_connection_string.return_value = mock_client

            with patch(
                "depotbutler.services.blob_storage_service.settings", mock_settings
            ):
                service = BlobStorageService()

                destination = tmp_path / "downloads" / "test.pdf"
                result = await service.download_to_file(
                    publication_id="test-pub",
                    date="2025-12-27",
                    filename="test.pdf",
                    destination=destination,
                )

                assert result is True
                assert destination.exists()
                assert destination.read_bytes() == test_pdf_bytes

    @pytest.mark.asyncio
    async def test_download_to_file_not_found(self, mock_settings, tmp_path):
        """Test download when file not in cache."""
        with patch(
            "depotbutler.services.blob_storage_service.BlobServiceClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_container = MagicMock()
            mock_blob_client = MagicMock()

            mock_container.exists.return_value = True
            mock_client.get_container_client.return_value = mock_container
            mock_container.get_blob_client.return_value = mock_blob_client
            mock_blob_client.exists.return_value = False  # Not found
            mock_client_class.from_connection_string.return_value = mock_client

            with patch(
                "depotbutler.services.blob_storage_service.settings", mock_settings
            ):
                service = BlobStorageService()

                destination = tmp_path / "test.pdf"
                result = await service.download_to_file(
                    publication_id="test-pub",
                    date="2025-12-27",
                    filename="test.pdf",
                    destination=destination,
                )

                assert result is False
                assert not destination.exists()

    @pytest.mark.asyncio
    async def test_archive_from_file_success(self, mock_settings, tmp_path):
        """Test successful archive from local file."""
        with patch(
            "depotbutler.services.blob_storage_service.BlobServiceClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_container = MagicMock()
            mock_blob_client = MagicMock()

            mock_container.exists.return_value = True
            mock_client.get_container_client.return_value = mock_container
            mock_container.get_blob_client.return_value = mock_blob_client
            mock_blob_client.url = "https://test.blob.core.windows.net/test.pdf"
            mock_client_class.from_connection_string.return_value = mock_client

            # Create test PDF file
            test_file = tmp_path / "test.pdf"
            test_content = b"%PDF-1.4\nTest PDF Content"
            test_file.write_bytes(test_content)

            with patch(
                "depotbutler.services.blob_storage_service.settings", mock_settings
            ):
                service = BlobStorageService()

                result = await service.archive_from_file(
                    file_path=test_file,
                    publication_id="test-pub",
                    date="2025-12-27",
                    metadata={"issue": "01/2025"},
                )

                assert "blob_url" in result
                assert "blob_path" in result
                assert result["blob_path"] == "test-pub/2025/test.pdf"
                mock_blob_client.upload_blob.assert_called_once()

    @pytest.mark.asyncio
    async def test_archive_from_file_not_found(self, mock_settings, tmp_path):
        """Test archive from file when file doesn't exist."""
        with patch(
            "depotbutler.services.blob_storage_service.BlobServiceClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_container = MagicMock()

            mock_container.exists.return_value = True
            mock_client.get_container_client.return_value = mock_container
            mock_client_class.from_connection_string.return_value = mock_client

            with patch(
                "depotbutler.services.blob_storage_service.settings", mock_settings
            ):
                service = BlobStorageService()

                nonexistent_file = tmp_path / "nonexistent.pdf"
                with pytest.raises(UploadError, match="File not found"):
                    await service.archive_from_file(
                        file_path=nonexistent_file,
                        publication_id="test-pub",
                        date="2025-12-27",
                    )


class TestBlobStorageServiceUpdateMetadata:
    """Test BlobStorageService update_metadata method."""

    @pytest.mark.asyncio
    async def test_update_metadata_success(self, mock_settings):
        """Test successful metadata update."""
        with patch(
            "depotbutler.services.blob_storage_service.BlobServiceClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_container = MagicMock()
            mock_blob_client = MagicMock()

            # Setup blob client mocks
            mock_container.exists.return_value = True
            mock_blob_client.exists.return_value = True

            # Mock existing blob properties
            mock_properties = MagicMock()
            mock_properties.metadata = {
                "title": "Original Title",
                "archived_at": "2024-01-01",
            }
            mock_blob_client.get_blob_properties.return_value = mock_properties

            mock_container.get_blob_client.return_value = mock_blob_client
            mock_client.get_container_client.return_value = mock_container
            mock_client_class.from_connection_string.return_value = mock_client

            with patch(
                "depotbutler.services.blob_storage_service.settings", mock_settings
            ):
                service = BlobStorageService()

                new_metadata = {"download_url": "https://example.com/file.pdf"}
                result = await service.update_metadata(
                    publication_id="test-pub",
                    date="2025-01-15",
                    filename="test.pdf",
                    metadata=new_metadata,
                )

                assert result is True
                mock_blob_client.set_blob_metadata.assert_called_once()

                # Verify merged metadata
                call_args = mock_blob_client.set_blob_metadata.call_args
                merged_metadata = call_args[0][0]
                assert "title" in merged_metadata
                assert "archived_at" in merged_metadata
                assert "download_url" in merged_metadata
                assert merged_metadata["download_url"] == "https://example.com/file.pdf"

    @pytest.mark.asyncio
    async def test_update_metadata_blob_not_found(self, mock_settings):
        """Test update_metadata when blob doesn't exist."""
        with patch(
            "depotbutler.services.blob_storage_service.BlobServiceClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_container = MagicMock()
            mock_blob_client = MagicMock()

            # Setup blob to not exist
            mock_container.exists.return_value = True
            mock_blob_client.exists.return_value = False

            mock_container.get_blob_client.return_value = mock_blob_client
            mock_client.get_container_client.return_value = mock_container
            mock_client_class.from_connection_string.return_value = mock_client

            with patch(
                "depotbutler.services.blob_storage_service.settings", mock_settings
            ):
                service = BlobStorageService()

                result = await service.update_metadata(
                    publication_id="test-pub",
                    date="2025-01-15",
                    filename="nonexistent.pdf",
                    metadata={"download_url": "https://example.com/file.pdf"},
                )

                assert result is False
                mock_blob_client.set_blob_metadata.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_metadata_merges_existing(self, mock_settings):
        """Test that update_metadata preserves existing metadata."""
        with patch(
            "depotbutler.services.blob_storage_service.BlobServiceClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_container = MagicMock()
            mock_blob_client = MagicMock()

            # Setup existing metadata with multiple fields
            mock_container.exists.return_value = True
            mock_blob_client.exists.return_value = True

            mock_properties = MagicMock()
            mock_properties.metadata = {
                "title": "Test Publication",
                "issue": "01/2025",
                "archived_at": "2025-01-01T12:00:00",
                "content_type": "application/pdf",
            }
            mock_blob_client.get_blob_properties.return_value = mock_properties

            mock_container.get_blob_client.return_value = mock_blob_client
            mock_client.get_container_client.return_value = mock_container
            mock_client_class.from_connection_string.return_value = mock_client

            with patch(
                "depotbutler.services.blob_storage_service.settings", mock_settings
            ):
                service = BlobStorageService()

                # Add new metadata fields
                new_metadata = {
                    "download_url": "https://example.com/file.pdf",
                    "web_sync_at": "2025-01-15T10:00:00",
                }
                result = await service.update_metadata(
                    publication_id="test-pub",
                    date="2025-01-15",
                    filename="test.pdf",
                    metadata=new_metadata,
                )

                assert result is True

                # Verify all fields preserved and new ones added
                call_args = mock_blob_client.set_blob_metadata.call_args
                merged_metadata = call_args[0][0]

                # Original fields preserved
                assert merged_metadata["title"] == "Test Publication"
                assert merged_metadata["issue"] == "01/2025"
                assert merged_metadata["archived_at"] == "2025-01-01T12:00:00"
                assert merged_metadata["content_type"] == "application/pdf"

                # New fields added
                assert merged_metadata["download_url"] == "https://example.com/file.pdf"
                assert merged_metadata["web_sync_at"] == "2025-01-15T10:00:00"

    @pytest.mark.asyncio
    async def test_update_metadata_sanitizes_german_umlauts(self, mock_settings):
        """Test that update_metadata sanitizes German umlauts for Azure Blob Storage."""
        with patch(
            "depotbutler.services.blob_storage_service.BlobServiceClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_container = MagicMock()
            mock_blob_client = MagicMock()

            mock_container.exists.return_value = True
            mock_blob_client.exists.return_value = True

            mock_properties = MagicMock()
            mock_properties.metadata = {}
            mock_blob_client.get_blob_properties.return_value = mock_properties

            mock_container.get_blob_client.return_value = mock_blob_client
            mock_client.get_container_client.return_value = mock_container
            mock_client_class.from_connection_string.return_value = mock_client

            with patch(
                "depotbutler.services.blob_storage_service.settings", mock_settings
            ):
                service = BlobStorageService()

                # Metadata with German umlauts
                new_metadata = {
                    "title": "Über Börse & Öl",
                    "description": "Aktionäre müssen aufpassen",
                }
                result = await service.update_metadata(
                    publication_id="test-pub",
                    date="2025-01-15",
                    filename="test.pdf",
                    metadata=new_metadata,
                )

                assert result is True

                # Verify sanitization
                call_args = mock_blob_client.set_blob_metadata.call_args
                sanitized_metadata = call_args[0][0]

                # Check German umlauts are converted
                assert "Ue" in sanitized_metadata["title"]  # Ü → Ue
                assert "Oe" in sanitized_metadata["title"]  # Ö → Oe
                assert "ae" in sanitized_metadata["description"]  # ä → ae
                assert "ue" in sanitized_metadata["description"]  # ü → ue

                # Verify no non-ASCII characters remain
                for value in sanitized_metadata.values():
                    assert all(
                        ord(c) < 128 for c in value
                    ), f"Non-ASCII found in: {value}"

    @pytest.mark.asyncio
    async def test_update_metadata_raises_transient_error(self, mock_settings):
        """Test that update_metadata raises TransientError on Azure failure."""
        from depotbutler.exceptions import TransientError

        with patch(
            "depotbutler.services.blob_storage_service.BlobServiceClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_container = MagicMock()
            mock_blob_client = MagicMock()

            mock_container.exists.return_value = True
            mock_blob_client.exists.return_value = True

            mock_properties = MagicMock()
            mock_properties.metadata = {}
            mock_blob_client.get_blob_properties.return_value = mock_properties

            # Simulate Azure failure
            mock_blob_client.set_blob_metadata.side_effect = Exception(
                "Azure service error"
            )

            mock_container.get_blob_client.return_value = mock_blob_client
            mock_client.get_container_client.return_value = mock_container
            mock_client_class.from_connection_string.return_value = mock_client

            with patch(
                "depotbutler.services.blob_storage_service.settings", mock_settings
            ):
                service = BlobStorageService()

                with pytest.raises(TransientError, match="Blob metadata update failed"):
                    await service.update_metadata(
                        publication_id="test-pub",
                        date="2025-01-15",
                        filename="test.pdf",
                        metadata={"download_url": "https://example.com/file.pdf"},
                    )


class TestSettingsConfiguration:
    """Test BlobStorageSettings configuration."""

    def test_is_configured_with_connection_string(self):
        """Test is_configured returns True when connection string is set."""
        from pydantic import SecretStr

        from depotbutler.settings import BlobStorageSettings

        settings = BlobStorageSettings(
            connection_string=SecretStr("test-connection-string"),
            enabled=True,
        )

        assert settings.is_configured() is True

    def test_is_configured_without_connection_string(self):
        """Test is_configured returns False when connection string is None."""
        from depotbutler.settings import BlobStorageSettings

        settings = BlobStorageSettings(
            connection_string=None,
            enabled=True,
        )

        assert settings.is_configured() is False

    def test_is_configured_disabled(self):
        """Test is_configured returns False when disabled."""
        from pydantic import SecretStr

        from depotbutler.settings import BlobStorageSettings

        settings = BlobStorageSettings(
            connection_string=SecretStr("test-connection-string"),
            enabled=False,
        )

        assert settings.is_configured() is False
