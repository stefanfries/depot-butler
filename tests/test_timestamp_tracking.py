"""Unit tests for granular timestamp tracking in edition processing."""

from datetime import datetime
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
        publication_date="2025-12-27",
    )


class TestTimestampTracking:
    """Test granular timestamp tracking functionality."""

    @pytest.mark.asyncio
    async def test_downloaded_at_timestamp_set_on_download(
        self, sample_edition, tmp_path
    ):
        """Test that downloaded_at timestamp is set when PDF is downloaded."""
        # Mock MongoDB service and edition repository
        mock_mongodb = AsyncMock()
        mock_edition_repo = AsyncMock()
        mock_mongodb.edition_repo = mock_edition_repo
        mock_edition_repo.mark_edition_processed = AsyncMock(return_value=True)

        with patch(
            "depotbutler.db.mongodb.get_mongodb_service",
            return_value=mock_mongodb,
        ):
            from depotbutler.services.publication_processing_service import (
                PublicationProcessingService,
            )

            # Mock dependencies
            mock_client = AsyncMock()
            mock_client.download_edition = AsyncMock()
            mock_onedrive = AsyncMock()
            mock_email = AsyncMock()
            mock_tracker = MagicMock()
            mock_tracker._generate_edition_key = MagicMock(
                return_value="2025-12-27_Test Edition 01/2025"
            )
            mock_settings = MagicMock()
            mock_settings.tracking.temp_dir = str(tmp_path)

            service = PublicationProcessingService(
                boersenmedien_client=mock_client,
                onedrive_service=mock_onedrive,
                email_service=mock_email,
                edition_tracker=mock_tracker,
                blob_service=None,
                settings=mock_settings,
                dry_run=False,
            )

            # Set current_publication_data that's needed for mark_edition_processed
            service.current_publication_data = {
                "publication_id": "test-publication",
                "name": "Test Publication",
            }

            # Download edition
            result = await service._download_edition(sample_edition)

            # Verify downloaded_at was set
            assert result is not None
            mock_edition_repo.mark_edition_processed.assert_called_once()
            call_kwargs = mock_edition_repo.mark_edition_processed.call_args[1]
            assert "downloaded_at" in call_kwargs
            assert isinstance(call_kwargs["downloaded_at"], datetime)
            assert call_kwargs["edition_key"] == "2025-12-27_Test Edition 01/2025"

    @pytest.mark.asyncio
    async def test_email_sent_at_timestamp_set_on_success(
        self, sample_edition, tmp_path
    ):
        """Test that email_sent_at timestamp is set after successful email delivery."""

        temp_file = tmp_path / "test.pdf"
        temp_file.write_bytes(b"%PDF-1.4\nTest PDF")

        # Mock MongoDB service and edition repository
        mock_mongodb = AsyncMock()
        mock_edition_repo = AsyncMock()
        mock_mongodb.edition_repo = mock_edition_repo
        mock_edition_repo.update_email_sent_timestamp = AsyncMock(return_value=True)
        mock_mongodb.get_recipients_for_publication = AsyncMock(return_value=[])

        with patch(
            "depotbutler.db.mongodb.get_mongodb_service",
            return_value=mock_mongodb,
        ):
            from depotbutler.services.publication_processing_service import (
                PublicationProcessingService,
            )

            # Mock dependencies
            mock_client = AsyncMock()
            mock_onedrive = AsyncMock()
            mock_email = AsyncMock()
            mock_email.send_pdf_to_recipients = AsyncMock(return_value=True)
            mock_tracker = MagicMock()
            mock_tracker._generate_edition_key = MagicMock(
                return_value="2025-12-27_Test Edition 01/2025"
            )
            mock_settings = MagicMock()

            service = PublicationProcessingService(
                boersenmedien_client=mock_client,
                onedrive_service=mock_onedrive,
                email_service=mock_email,
                edition_tracker=mock_tracker,
                blob_service=None,
                settings=mock_settings,
                dry_run=False,
            )

            # Set current publication data
            service.current_publication_data = {"publication_id": "test-pub"}

            # Send email
            result = await service._send_pdf_email(sample_edition, str(temp_file))

            # Verify email_sent_at was set
            assert result is True
            mock_edition_repo.update_email_sent_timestamp.assert_called_once_with(
                "2025-12-27_Test Edition 01/2025"
            )

    @pytest.mark.asyncio
    async def test_email_sent_at_not_set_on_failure(self, sample_edition, tmp_path):
        """Test that email_sent_at timestamp is NOT set when email delivery fails."""

        temp_file = tmp_path / "test.pdf"
        temp_file.write_bytes(b"%PDF-1.4\nTest PDF")

        # Mock MongoDB service
        mock_mongodb = AsyncMock()
        mock_edition_repo = AsyncMock()
        mock_mongodb.edition_repo = mock_edition_repo
        mock_edition_repo.update_email_sent_timestamp = AsyncMock(return_value=True)

        with patch(
            "depotbutler.db.mongodb.get_mongodb_service",
            return_value=mock_mongodb,
        ):
            from depotbutler.services.publication_processing_service import (
                PublicationProcessingService,
            )

            # Mock dependencies with email failure
            mock_client = AsyncMock()
            mock_onedrive = AsyncMock()
            mock_email = AsyncMock()
            mock_email.send_pdf_to_recipients = AsyncMock(return_value=False)  # FAIL
            mock_tracker = MagicMock()
            mock_settings = MagicMock()

            service = PublicationProcessingService(
                boersenmedien_client=mock_client,
                onedrive_service=mock_onedrive,
                email_service=mock_email,
                edition_tracker=mock_tracker,
                blob_service=None,
                settings=mock_settings,
                dry_run=False,
            )

            service.current_publication_data = {"publication_id": "test-pub"}

            # Send email (fails)
            result = await service._send_pdf_email(sample_edition, str(temp_file))

            # Verify email_sent_at was NOT called
            assert result is False
            mock_edition_repo.update_email_sent_timestamp.assert_not_called()

    @pytest.mark.asyncio
    async def test_onedrive_uploaded_at_timestamp_set_on_success(
        self, sample_edition, tmp_path
    ):
        """Test that onedrive_uploaded_at timestamp is set after successful upload."""
        from depotbutler.models import UploadResult

        temp_file = tmp_path / "test.pdf"
        temp_file.write_bytes(b"%PDF-1.4\nTest PDF")

        # Mock MongoDB service
        mock_mongodb = AsyncMock()
        mock_edition_repo = AsyncMock()
        mock_mongodb.edition_repo = mock_edition_repo
        mock_edition_repo.update_onedrive_uploaded_timestamp = AsyncMock(
            return_value=True
        )

        # Mock recipient retrieval
        async def mock_get_recipients(publication_id: str, delivery_method: str):
            from tests.helpers.workflow_setup import create_mock_recipient

            return [
                create_mock_recipient(
                    publication_id=publication_id, upload_enabled=True
                )
            ]

        mock_mongodb.get_recipients_for_publication = AsyncMock(
            side_effect=mock_get_recipients
        )

        with patch(
            "depotbutler.db.mongodb.get_mongodb_service",
            return_value=mock_mongodb,
        ):
            from depotbutler.services.publication_processing_service import (
                PublicationProcessingService,
            )

            # Mock dependencies
            mock_client = AsyncMock()
            mock_onedrive = AsyncMock()
            mock_onedrive.authenticate = AsyncMock(return_value=True)
            mock_onedrive.upload_file = AsyncMock(
                return_value=UploadResult(
                    success=True,
                    file_url="https://onedrive.com/test.pdf",
                    file_id="test-id",
                )
            )
            mock_email = AsyncMock()
            mock_tracker = MagicMock()
            mock_tracker._generate_edition_key = MagicMock(
                return_value="2025-12-27_Test Edition 01/2025"
            )
            mock_settings = MagicMock()

            service = PublicationProcessingService(
                boersenmedien_client=mock_client,
                onedrive_service=mock_onedrive,
                email_service=mock_email,
                edition_tracker=mock_tracker,
                blob_service=None,
                settings=mock_settings,
                dry_run=False,
            )

            service.current_publication_data = {
                "publication_id": "test-pub",
                "default_onedrive_folder": "test-folder",
                "organize_by_year": True,
            }

            # Upload to OneDrive (using new delivery service)
            result = await service.delivery_service.upload_for_recipients(
                sample_edition, str(temp_file), service.current_publication_data
            )

            # Verify onedrive_uploaded_at was set
            assert result.success is True
            mock_edition_repo.update_onedrive_uploaded_timestamp.assert_called_once_with(
                "2025-12-27_Test Edition 01/2025"
            )

    @pytest.mark.asyncio
    async def test_onedrive_uploaded_at_not_set_on_failure(
        self, sample_edition, tmp_path
    ):
        """Test that onedrive_uploaded_at timestamp is NOT set when upload fails."""
        from depotbutler.models import UploadResult

        temp_file = tmp_path / "test.pdf"
        temp_file.write_bytes(b"%PDF-1.4\nTest PDF")

        # Mock MongoDB service
        mock_mongodb = AsyncMock()
        mock_edition_repo = AsyncMock()
        mock_mongodb.edition_repo = mock_edition_repo
        mock_edition_repo.update_onedrive_uploaded_timestamp = AsyncMock(
            return_value=True
        )

        with patch(
            "depotbutler.db.mongodb.get_mongodb_service",
            return_value=mock_mongodb,
        ):
            from depotbutler.services.publication_processing_service import (
                PublicationProcessingService,
            )

            # Mock dependencies with upload failure
            mock_client = AsyncMock()
            mock_onedrive = AsyncMock()
            mock_onedrive.authenticate = AsyncMock(return_value=True)
            mock_onedrive.upload_file = AsyncMock(
                return_value=UploadResult(
                    success=False,
                    error="Upload failed",
                )
            )
            mock_email = AsyncMock()
            mock_tracker = MagicMock()
            mock_settings = MagicMock()

            service = PublicationProcessingService(
                boersenmedien_client=mock_client,
                onedrive_service=mock_onedrive,
                email_service=mock_email,
                edition_tracker=mock_tracker,
                blob_service=None,
                settings=mock_settings,
                dry_run=False,
            )

            service.current_publication_data = {
                "publication_id": "test-pub",
                "default_onedrive_folder": "test-folder",
                "organize_by_year": True,
            }

            # Upload to OneDrive (fails) - using new delivery service
            result = await service.delivery_service.upload_for_recipients(
                sample_edition, str(temp_file), service.current_publication_data
            )

            # Verify onedrive_uploaded_at was NOT called
            assert result.success is False
            mock_edition_repo.update_onedrive_uploaded_timestamp.assert_not_called()


class TestEditionRepositoryTimestampMethods:
    """Test EditionRepository timestamp update methods."""

    @pytest.mark.asyncio
    async def test_update_email_sent_timestamp(self):
        """Test update_email_sent_timestamp method."""
        from depotbutler.db.repositories.edition import EditionRepository

        mock_client = AsyncMock()
        mock_db = MagicMock()
        mock_collection = AsyncMock()
        mock_result = MagicMock()
        mock_result.modified_count = 1
        mock_collection.update_one = AsyncMock(return_value=mock_result)
        mock_client.__getitem__ = MagicMock(return_value=mock_db)
        mock_db.processed_editions = mock_collection

        repo = EditionRepository(client=mock_client, db_name="test_db")

        result = await repo.update_email_sent_timestamp("test-edition-key")

        assert result is True
        mock_collection.update_one.assert_called_once()
        call_args = mock_collection.update_one.call_args
        assert call_args[0][0] == {"edition_key": "test-edition-key"}
        assert "email_sent_at" in call_args[0][1]["$set"]

    @pytest.mark.asyncio
    async def test_update_onedrive_uploaded_timestamp(self):
        """Test update_onedrive_uploaded_timestamp method."""
        from depotbutler.db.repositories.edition import EditionRepository

        mock_client = AsyncMock()
        mock_db = MagicMock()
        mock_collection = AsyncMock()
        mock_result = MagicMock()
        mock_result.modified_count = 1
        mock_collection.update_one = AsyncMock(return_value=mock_result)
        mock_client.__getitem__ = MagicMock(return_value=mock_db)
        mock_db.processed_editions = mock_collection

        repo = EditionRepository(client=mock_client, db_name="test_db")

        result = await repo.update_onedrive_uploaded_timestamp("test-edition-key")

        assert result is True
        mock_collection.update_one.assert_called_once()
        call_args = mock_collection.update_one.call_args
        assert call_args[0][0] == {"edition_key": "test-edition-key"}
        assert "onedrive_uploaded_at" in call_args[0][1]["$set"]

    @pytest.mark.asyncio
    async def test_update_blob_metadata(self):
        """Test update_blob_metadata method."""
        from depotbutler.db.repositories.edition import EditionRepository

        mock_client = AsyncMock()
        mock_db = MagicMock()
        mock_collection = AsyncMock()
        mock_result = MagicMock()
        mock_result.modified_count = 1
        mock_collection.update_one = AsyncMock(return_value=mock_result)
        mock_client.__getitem__ = MagicMock(return_value=mock_db)
        mock_db.processed_editions = mock_collection

        repo = EditionRepository(client=mock_client, db_name="test_db")

        result = await repo.update_blob_metadata(
            edition_key="test-edition-key",
            blob_url="https://blob.storage/test.pdf",
            blob_path="2025/test-pub/test.pdf",
            blob_container="editions",
            file_size_bytes=12345,
        )

        assert result is True
        mock_collection.update_one.assert_called_once()
        call_args = mock_collection.update_one.call_args
        assert call_args[0][0] == {"edition_key": "test-edition-key"}
        update_doc = call_args[0][1]["$set"]
        assert update_doc["blob_url"] == "https://blob.storage/test.pdf"
        assert update_doc["blob_path"] == "2025/test-pub/test.pdf"
        assert update_doc["blob_container"] == "editions"
        assert update_doc["file_size_bytes"] == 12345
        assert "archived_at" in update_doc
