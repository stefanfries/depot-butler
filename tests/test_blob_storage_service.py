"""Unit tests for BlobStorageService."""

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
                    == "2025/megatrend-folger/2025-12-27_Megatrend-Folger_51-2025.pdf"
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

                assert path == "2024/test-pub/test.pdf"


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
                assert result["blob_path"] == "2025/test-pub/test.pdf"
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
