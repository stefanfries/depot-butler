"""Unit tests for publication delivery statistics tracking."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestPublicationStatisticsUpdate:
    """Test publication delivery statistics update functionality."""

    @pytest.mark.asyncio
    async def test_update_statistics_increments_delivery_count(self):
        """Test that delivery_count is incremented after successful delivery."""
        # Mock MongoDB service
        mock_mongodb = AsyncMock()
        mock_collection = AsyncMock()
        mock_mongodb.db.publications = mock_collection
        mock_collection.update_one = AsyncMock()

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

            # Call the method
            await service._update_publication_statistics("test-publication")

            # Verify update_one was called with correct parameters
            mock_collection.update_one.assert_called_once()
            call_args = mock_collection.update_one.call_args

            # Check filter
            assert call_args[0][0] == {"publication_id": "test-publication"}

            # Check update operations
            update_ops = call_args[0][1]
            assert "$inc" in update_ops
            assert update_ops["$inc"]["delivery_count"] == 1
            assert "$set" in update_ops
            assert "last_delivered_at" in update_ops["$set"]
            assert isinstance(update_ops["$set"]["last_delivered_at"], datetime)

    @pytest.mark.asyncio
    async def test_update_statistics_sets_timestamp(self):
        """Test that last_delivered_at timestamp is set correctly."""
        # Mock MongoDB service
        mock_mongodb = AsyncMock()
        mock_collection = AsyncMock()
        mock_mongodb.db.publications = mock_collection
        mock_collection.update_one = AsyncMock()

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

            # Call the method
            await service._update_publication_statistics("megatrend-folger")

            # Verify timestamp was set
            call_args = mock_collection.update_one.call_args
            update_ops = call_args[0][1]

            timestamp = update_ops["$set"]["last_delivered_at"]
            assert isinstance(timestamp, datetime)
            # Timestamp should be recent (within last second)
            from datetime import UTC

            now = datetime.now(UTC)
            assert (now - timestamp).total_seconds() < 1

    @pytest.mark.asyncio
    async def test_update_statistics_skipped_in_dry_run(self):
        """Test that statistics are not updated in dry-run mode."""
        # Mock MongoDB service
        mock_mongodb = AsyncMock()
        mock_collection = AsyncMock()
        mock_mongodb.db.publications = mock_collection
        mock_collection.update_one = AsyncMock()

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
            mock_tracker = MagicMock()
            mock_settings = MagicMock()

            service = PublicationProcessingService(
                boersenmedien_client=mock_client,
                onedrive_service=mock_onedrive,
                email_service=mock_email,
                edition_tracker=mock_tracker,
                blob_service=None,
                settings=mock_settings,
                dry_run=True,  # Enable dry-run mode
            )

            # Call the method
            await service._update_publication_statistics("test-publication")

            # Verify update_one was NOT called
            mock_collection.update_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_statistics_handles_error_gracefully(self):
        """Test that errors in statistics update don't crash the workflow."""
        # Mock MongoDB service that raises an error
        mock_mongodb = AsyncMock()
        mock_collection = AsyncMock()
        mock_mongodb.db.publications = mock_collection
        mock_collection.update_one = AsyncMock(
            side_effect=Exception("Database connection failed")
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

            # Should not raise an exception
            try:
                await service._update_publication_statistics("test-publication")
            except Exception as e:
                pytest.fail(f"Method should not raise exceptions: {e}")

            # Verify update was attempted
            mock_collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_statistics_with_multiple_publications(self):
        """Test that statistics are tracked separately for multiple publications."""
        # Mock MongoDB service
        mock_mongodb = AsyncMock()
        mock_collection = AsyncMock()
        mock_mongodb.db.publications = mock_collection
        mock_collection.update_one = AsyncMock()

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

            # Call for first publication
            await service._update_publication_statistics("megatrend-folger")

            # Call for second publication
            await service._update_publication_statistics("der-aktionaer-epaper")

            # Verify both were updated separately
            assert mock_collection.update_one.call_count == 2

            # Check first call
            first_call = mock_collection.update_one.call_args_list[0]
            assert first_call[0][0] == {"publication_id": "megatrend-folger"}

            # Check second call
            second_call = mock_collection.update_one.call_args_list[1]
            assert second_call[0][0] == {"publication_id": "der-aktionaer-epaper"}
