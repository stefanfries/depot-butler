"""Unit tests for blob archival integration in publication processing."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from depotbutler.models import Edition


@pytest.fixture
def sample_edition():
    """Sample edition for testing."""
    return Edition(
        title="Test Edition 01/2025",
        details_url="https://example.com/details/test",
        download_url="https://example.com/download/test.pdf",
        publication_date="2025-12-28",
    )


@pytest.fixture
def sample_pdf_bytes():
    """Sample PDF bytes for testing."""
    return b"%PDF-1.4\nTest PDF content\n%%EOF"


class TestBlobArchival:
    """Test blob archival functionality."""

    @pytest.mark.asyncio
    async def test_archive_to_blob_storage_success(
        self, sample_edition, sample_pdf_bytes, tmp_path
    ):
        """Test successful blob archival after delivery."""
        from depotbutler.services.publication_processing_service import (
            PublicationProcessingService,
        )

        # Create temp PDF file
        temp_file = tmp_path / "test.pdf"
        temp_file.write_bytes(sample_pdf_bytes)

        # Mock blob service
        mock_blob_service = AsyncMock()
        mock_blob_service.archive_edition = AsyncMock(
            return_value={
                "blob_url": "https://blob.storage/2025/test-pub/test.pdf",
                "blob_path": "2025/test-pub/test.pdf",
                "blob_container": "editions",
                "file_size_bytes": "123456",
                "archived_at": "2025-12-28T10:00:00Z",
            }
        )

        # Mock MongoDB
        mock_mongodb = AsyncMock()
        mock_edition_repo = AsyncMock()
        mock_mongodb.edition_repo = mock_edition_repo
        mock_edition_repo.update_blob_metadata = AsyncMock(return_value=True)

        with patch(
            "depotbutler.db.mongodb.get_mongodb_service",
            return_value=mock_mongodb,
        ):
            # Create service
            mock_client = AsyncMock()
            mock_onedrive = AsyncMock()
            mock_email = AsyncMock()
            mock_tracker = MagicMock()
            mock_tracker._generate_edition_key = MagicMock(
                return_value="2025-12-28_Test Edition 01/2025"
            )
            mock_settings = MagicMock()

            service = PublicationProcessingService(
                boersenmedien_client=mock_client,
                onedrive_service=mock_onedrive,
                email_service=mock_email,
                edition_tracker=mock_tracker,
                blob_service=mock_blob_service,
                settings=mock_settings,
                dry_run=False,
                use_cache=False,
            )

            # Set publication data
            service.current_publication_data = {"publication_id": "test-pub"}

            # Archive to blob storage
            await service._archive_to_blob_storage(sample_edition, str(temp_file))

            # Verify blob service was called
            mock_blob_service.archive_edition.assert_called_once()
            call_kwargs = mock_blob_service.archive_edition.call_args[1]
            assert call_kwargs["pdf_bytes"] == sample_pdf_bytes
            assert call_kwargs["publication_id"] == "test-pub"
            assert call_kwargs["date"] == "2025-12-28"

            # Verify MongoDB was updated
            mock_edition_repo.update_blob_metadata.assert_called_once()
            metadata_call = mock_edition_repo.update_blob_metadata.call_args[1]
            assert metadata_call["edition_key"] == "2025-12-28_Test Edition 01/2025"
            assert (
                metadata_call["blob_url"]
                == "https://blob.storage/2025/test-pub/test.pdf"
            )

    @pytest.mark.asyncio
    async def test_archive_to_blob_storage_disabled(self, sample_edition, tmp_path):
        """Test archival skipped when blob service not configured."""
        from depotbutler.services.publication_processing_service import (
            PublicationProcessingService,
        )

        temp_file = tmp_path / "test.pdf"
        temp_file.write_bytes(b"%PDF-1.4\nTest")

        # Create service WITHOUT blob service
        service = PublicationProcessingService(
            boersenmedien_client=AsyncMock(),
            onedrive_service=AsyncMock(),
            email_service=AsyncMock(),
            edition_tracker=MagicMock(),
            blob_service=None,  # No blob service
            settings=MagicMock(),
            dry_run=False,
            use_cache=False,
        )

        service.current_publication_data = {"publication_id": "test-pub"}

        # Archive (should return silently without error)
        await service._archive_to_blob_storage(sample_edition, str(temp_file))

        # No assertions needed - just verify it doesn't crash

    @pytest.mark.asyncio
    async def test_archive_to_blob_storage_dry_run(self, sample_edition, tmp_path):
        """Test archival skipped in dry-run mode."""
        from depotbutler.services.publication_processing_service import (
            PublicationProcessingService,
        )

        temp_file = tmp_path / "test.pdf"
        temp_file.write_bytes(b"%PDF-1.4\nTest")

        mock_blob_service = AsyncMock()
        mock_blob_service.archive_edition = AsyncMock()

        service = PublicationProcessingService(
            boersenmedien_client=AsyncMock(),
            onedrive_service=AsyncMock(),
            email_service=AsyncMock(),
            edition_tracker=MagicMock(),
            blob_service=mock_blob_service,
            settings=MagicMock(),
            dry_run=True,  # Dry-run mode
            use_cache=False,
        )

        service.current_publication_data = {"publication_id": "test-pub"}

        # Archive in dry-run mode
        await service._archive_to_blob_storage(sample_edition, str(temp_file))

        # Verify blob service was NOT called
        mock_blob_service.archive_edition.assert_not_called()

    @pytest.mark.asyncio
    async def test_archive_to_blob_storage_non_blocking_error(
        self, sample_edition, tmp_path
    ):
        """Test that blob archival errors don't fail the workflow."""
        from unittest.mock import patch

        from depotbutler.services.publication_processing_service import (
            PublicationProcessingService,
        )

        temp_file = tmp_path / "test.pdf"
        temp_file.write_bytes(b"%PDF-1.4\nTest")

        # Mock blob service that raises an error
        mock_blob_service = AsyncMock()
        mock_blob_service.archive_edition = AsyncMock(
            side_effect=Exception("Blob storage failure")
        )

        service = PublicationProcessingService(
            boersenmedien_client=AsyncMock(),
            onedrive_service=AsyncMock(),
            email_service=AsyncMock(),
            edition_tracker=MagicMock(),
            blob_service=mock_blob_service,
            settings=MagicMock(),
            dry_run=False,
            use_cache=False,
        )

        service.current_publication_data = {
            "publication_id": "test-pub",
            "default_onedrive_folder": "Test/Folder",
        }

        # Mock MongoDB service
        with patch("depotbutler.db.mongodb.get_mongodb_service") as mock_mongodb:
            mock_db = AsyncMock()
            mock_db.edition_repo = AsyncMock()
            mock_db.edition_repo.update_blob_metadata = AsyncMock()
            mock_db.get_app_config = AsyncMock(return_value=True)
            mock_mongodb.return_value = mock_db

            # Archive (should NOT raise exception despite error)
            await service._archive_to_blob_storage(sample_edition, str(temp_file))

        # Verify it attempted the call
        mock_blob_service.archive_edition.assert_called_once()


class TestCacheFunctionality:
    """Test --use-cache flag functionality."""

    @pytest.mark.asyncio
    async def test_cache_hit_skips_download(self, sample_edition, tmp_path):
        """Test cache hit skips website download."""
        from depotbutler.services.publication_processing_service import (
            PublicationProcessingService,
        )

        cached_pdf = b"%PDF-1.4\nCached PDF\n%%EOF"

        # Mock blob service with cached PDF
        mock_blob_service = AsyncMock()
        mock_blob_service.get_cached_edition = AsyncMock(return_value=cached_pdf)

        mock_client = AsyncMock()
        mock_client.download_edition = AsyncMock()  # Should NOT be called

        mock_settings = MagicMock()
        mock_settings.tracking.temp_dir = str(tmp_path)

        service = PublicationProcessingService(
            boersenmedien_client=mock_client,
            onedrive_service=AsyncMock(),
            email_service=AsyncMock(),
            edition_tracker=MagicMock(),
            blob_service=mock_blob_service,
            settings=mock_settings,
            dry_run=False,
            use_cache=True,  # Cache enabled
        )

        service.current_publication_data = {"publication_id": "test-pub"}

        # Download (should use cache)
        result = await service._download_edition(sample_edition)

        # Verify cache was checked
        mock_blob_service.get_cached_edition.assert_called_once()

        # Verify website download was NOT called
        mock_client.download_edition.assert_not_called()

        # Verify file was created from cache
        assert result is not None
        downloaded_file = Path(result)
        assert downloaded_file.exists()
        assert downloaded_file.read_bytes() == cached_pdf

    @pytest.mark.asyncio
    async def test_cache_miss_falls_back_to_download(self, sample_edition, tmp_path):
        """Test cache miss falls back to website download."""
        from depotbutler.services.publication_processing_service import (
            PublicationProcessingService,
        )

        # Mock blob service with cache miss
        mock_blob_service = AsyncMock()
        mock_blob_service.get_cached_edition = AsyncMock(return_value=None)

        mock_client = AsyncMock()
        mock_client.download_edition = AsyncMock()

        # Mock MongoDB
        mock_mongodb = AsyncMock()
        mock_edition_repo = AsyncMock()
        mock_mongodb.edition_repo = mock_edition_repo
        mock_edition_repo.mark_edition_processed = AsyncMock(return_value=True)

        mock_settings = MagicMock()
        mock_settings.tracking.temp_dir = str(tmp_path)

        with patch(
            "depotbutler.db.mongodb.get_mongodb_service",
            return_value=mock_mongodb,
        ):
            service = PublicationProcessingService(
                boersenmedien_client=mock_client,
                onedrive_service=AsyncMock(),
                email_service=AsyncMock(),
                edition_tracker=MagicMock(),
                blob_service=mock_blob_service,
                settings=mock_settings,
                dry_run=False,
                use_cache=True,  # Cache enabled
            )

            service.current_publication_data = {"publication_id": "test-pub"}

            # Download (should fall back to website)
            result = await service._download_edition(sample_edition)

            # Verify cache was checked
            mock_blob_service.get_cached_edition.assert_called_once()

            # Verify website download WAS called as fallback
            mock_client.download_edition.assert_called_once()

            assert result is not None

    @pytest.mark.asyncio
    async def test_cache_disabled_always_downloads(self, sample_edition, tmp_path):
        """Test that cache is not checked when use_cache=False."""
        from depotbutler.services.publication_processing_service import (
            PublicationProcessingService,
        )

        mock_blob_service = AsyncMock()
        mock_blob_service.get_cached_edition = AsyncMock(
            return_value=b"Cached PDF"
        )  # Should NOT be called

        mock_client = AsyncMock()
        mock_client.download_edition = AsyncMock()

        # Mock MongoDB
        mock_mongodb = AsyncMock()
        mock_edition_repo = AsyncMock()
        mock_mongodb.edition_repo = mock_edition_repo
        mock_edition_repo.mark_edition_processed = AsyncMock(return_value=True)

        mock_settings = MagicMock()
        mock_settings.tracking.temp_dir = str(tmp_path)

        with patch(
            "depotbutler.db.mongodb.get_mongodb_service",
            return_value=mock_mongodb,
        ):
            service = PublicationProcessingService(
                boersenmedien_client=mock_client,
                onedrive_service=AsyncMock(),
                email_service=AsyncMock(),
                edition_tracker=MagicMock(),
                blob_service=mock_blob_service,
                settings=mock_settings,
                dry_run=False,
                use_cache=False,  # Cache DISABLED
            )

            service.current_publication_data = {"publication_id": "test-pub"}

            # Download (should skip cache entirely)
            result = await service._download_edition(sample_edition)

            # Verify cache was NOT checked
            mock_blob_service.get_cached_edition.assert_not_called()

            # Verify website download WAS called
            mock_client.download_edition.assert_called_once()

            assert result is not None

    @pytest.mark.asyncio
    async def test_cache_with_no_blob_service(self, sample_edition, tmp_path):
        """Test use_cache=True gracefully handles missing blob service."""
        from depotbutler.services.publication_processing_service import (
            PublicationProcessingService,
        )

        mock_client = AsyncMock()
        mock_client.download_edition = AsyncMock()

        # Mock MongoDB
        mock_mongodb = AsyncMock()
        mock_edition_repo = AsyncMock()
        mock_mongodb.edition_repo = mock_edition_repo
        mock_edition_repo.mark_edition_processed = AsyncMock(return_value=True)

        mock_settings = MagicMock()
        mock_settings.tracking.temp_dir = str(tmp_path)

        with patch(
            "depotbutler.db.mongodb.get_mongodb_service",
            return_value=mock_mongodb,
        ):
            service = PublicationProcessingService(
                boersenmedien_client=mock_client,
                onedrive_service=AsyncMock(),
                email_service=AsyncMock(),
                edition_tracker=MagicMock(),
                blob_service=None,  # No blob service
                settings=mock_settings,
                dry_run=False,
                use_cache=True,  # Cache enabled but no service
            )

            service.current_publication_data = {"publication_id": "test-pub"}

            # Download (should skip cache check and download directly)
            result = await service._download_edition(sample_edition)

            # Verify website download WAS called
            mock_client.download_edition.assert_called_once()

            assert result is not None
