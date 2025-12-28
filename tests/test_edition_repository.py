"""Unit tests for EditionRepository."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from depotbutler.db.repositories.edition import EditionRepository


@pytest.fixture
def edition_repo():
    """Mock EditionRepository with AsyncMock collection."""
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_collection = AsyncMock()

    # Mock the processed_editions collection
    mock_db.processed_editions = mock_collection
    mock_client.__getitem__ = MagicMock(return_value=mock_db)

    repo = EditionRepository(client=mock_client, db_name="test_db")
    return repo


class TestIsEditionProcessed:
    """Tests for is_edition_processed method."""

    @pytest.mark.asyncio
    async def test_returns_true_when_edition_exists(self, edition_repo):
        """Edition exists - should return True."""
        edition_repo.collection.find_one = AsyncMock(
            return_value={"edition_key": "2024-01-15_test"}
        )

        result = await edition_repo.is_edition_processed("2024-01-15_test")

        assert result is True
        edition_repo.collection.find_one.assert_called_once_with(
            {"edition_key": "2024-01-15_test"}
        )

    @pytest.mark.asyncio
    async def test_returns_false_when_edition_not_found(self, edition_repo):
        """Edition doesn't exist - should return False."""
        edition_repo.collection.find_one = AsyncMock(return_value=None)

        result = await edition_repo.is_edition_processed("2024-01-15_test")

        assert result is False

    @pytest.mark.asyncio
    async def test_handles_database_error(self, edition_repo):
        """Database error - should return False."""
        edition_repo.collection.find_one = AsyncMock(side_effect=Exception("DB error"))

        result = await edition_repo.is_edition_processed("2024-01-15_test")

        assert result is False


class TestMarkEditionProcessed:
    """Tests for mark_edition_processed method."""

    @pytest.mark.asyncio
    async def test_marks_edition_with_all_fields(self, edition_repo):
        """Mark edition with all optional fields provided."""
        edition_repo.collection.update_one = AsyncMock()
        now = datetime.now(UTC)

        result = await edition_repo.mark_edition_processed(
            edition_key="2024-01-15_test",
            title="Test Edition",
            publication_date="2024-01-15",
            download_url="https://example.com/test.pdf",
            file_path="/tmp/test.pdf",
            downloaded_at=now,
            blob_url="https://blob.storage/test.pdf",
            blob_path="editions/test.pdf",
            blob_container="editions",
            file_size_bytes=1024,
            archived_at=now,
        )

        assert result is True
        edition_repo.collection.update_one.assert_called_once()

        # Verify update_one was called with correct structure
        call_args = edition_repo.collection.update_one.call_args
        assert call_args[0][0] == {"edition_key": "2024-01-15_test"}
        assert "$set" in call_args[0][1]
        assert call_args[1]["upsert"] is True

    @pytest.mark.asyncio
    async def test_marks_edition_with_minimal_fields(self, edition_repo):
        """Mark edition with only required fields."""
        edition_repo.collection.update_one = AsyncMock()

        result = await edition_repo.mark_edition_processed(
            edition_key="2024-01-15_test",
            title="Test Edition",
            publication_date="2024-01-15",
            download_url="https://example.com/test.pdf",
        )

        assert result is True
        call_args = edition_repo.collection.update_one.call_args
        update_doc = call_args[0][1]["$set"]

        # Should have required fields
        assert update_doc["edition_key"] == "2024-01-15_test"
        assert update_doc["title"] == "Test Edition"
        assert "processed_at" in update_doc

        # Should not have optional fields when not provided
        assert "blob_url" not in update_doc
        assert "file_size_bytes" not in update_doc

    @pytest.mark.asyncio
    async def test_handles_database_error(self, edition_repo):
        """Database error - should return False."""
        edition_repo.collection.update_one = AsyncMock(
            side_effect=Exception("DB error")
        )

        result = await edition_repo.mark_edition_processed(
            edition_key="2024-01-15_test",
            title="Test",
            publication_date="2024-01-15",
            download_url="https://example.com/test.pdf",
        )

        assert result is False


class TestUpdateTimestamps:
    """Tests for timestamp update methods."""

    @pytest.mark.asyncio
    async def test_update_email_sent_timestamp_success(self, edition_repo):
        """Successfully update email_sent_at timestamp."""
        mock_result = MagicMock()
        mock_result.modified_count = 1
        edition_repo.collection.update_one = AsyncMock(return_value=mock_result)

        result = await edition_repo.update_email_sent_timestamp("2024-01-15_test")

        assert result is True
        edition_repo.collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_email_sent_timestamp_not_found(self, edition_repo):
        """Edition not found - should return False."""
        mock_result = MagicMock()
        mock_result.modified_count = 0
        edition_repo.collection.update_one = AsyncMock(return_value=mock_result)

        result = await edition_repo.update_email_sent_timestamp("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_update_onedrive_uploaded_timestamp_success(self, edition_repo):
        """Successfully update onedrive_uploaded_at timestamp."""
        mock_result = MagicMock()
        mock_result.modified_count = 1
        edition_repo.collection.update_one = AsyncMock(return_value=mock_result)

        result = await edition_repo.update_onedrive_uploaded_timestamp(
            "2024-01-15_test"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_update_timestamps_with_custom_time(self, edition_repo):
        """Update timestamp with custom datetime."""
        mock_result = MagicMock()
        mock_result.modified_count = 1
        edition_repo.collection.update_one = AsyncMock(return_value=mock_result)
        custom_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)

        result = await edition_repo.update_email_sent_timestamp(
            "2024-01-15_test", custom_time
        )

        assert result is True
        call_args = edition_repo.collection.update_one.call_args
        assert call_args[0][1]["$set"]["email_sent_at"] == custom_time


class TestUpdateBlobMetadata:
    """Tests for update_blob_metadata method."""

    @pytest.mark.asyncio
    async def test_update_blob_metadata_success(self, edition_repo):
        """Successfully update blob metadata."""
        mock_result = MagicMock()
        mock_result.modified_count = 1
        edition_repo.collection.update_one = AsyncMock(return_value=mock_result)

        result = await edition_repo.update_blob_metadata(
            edition_key="2024-01-15_test",
            blob_url="https://blob.storage/test.pdf",
            blob_path="editions/test.pdf",
            blob_container="editions",
            file_size_bytes=2048,
        )

        assert result is True
        call_args = edition_repo.collection.update_one.call_args
        update_doc = call_args[0][1]["$set"]

        assert update_doc["blob_url"] == "https://blob.storage/test.pdf"
        assert update_doc["blob_path"] == "editions/test.pdf"
        assert update_doc["blob_container"] == "editions"
        assert update_doc["file_size_bytes"] == 2048
        assert "archived_at" in update_doc

    @pytest.mark.asyncio
    async def test_update_blob_metadata_not_found(self, edition_repo):
        """Edition not found - should return False."""
        mock_result = MagicMock()
        mock_result.modified_count = 0
        edition_repo.collection.update_one = AsyncMock(return_value=mock_result)

        result = await edition_repo.update_blob_metadata(
            edition_key="nonexistent",
            blob_url="https://blob.storage/test.pdf",
            blob_path="editions/test.pdf",
            blob_container="editions",
            file_size_bytes=2048,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_update_blob_metadata_database_error(self, edition_repo):
        """Database error - should return False."""
        edition_repo.collection.update_one = AsyncMock(
            side_effect=Exception("DB error")
        )

        result = await edition_repo.update_blob_metadata(
            edition_key="2024-01-15_test",
            blob_url="https://blob.storage/test.pdf",
            blob_path="editions/test.pdf",
            blob_container="editions",
            file_size_bytes=2048,
        )

        assert result is False


class TestGetProcessedEditions:
    """Tests for get_recent_processed_editions and count methods."""

    @pytest.mark.asyncio
    async def test_get_processed_editions_count(self, edition_repo):
        """Get count of all processed editions."""
        edition_repo.collection.count_documents = AsyncMock(return_value=42)

        result = await edition_repo.get_processed_editions_count()

        assert result == 42
        edition_repo.collection.count_documents.assert_called_once_with({})

    @pytest.mark.asyncio
    async def test_get_recent_processed_editions(self, edition_repo):
        """Get editions from last N days."""
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(
            return_value=[
                {"edition_key": "2024-01-15_test1"},
                {"edition_key": "2024-01-14_test2"},
            ]
        )
        mock_cursor.sort = MagicMock(return_value=mock_cursor)

        edition_repo.collection.find = MagicMock(return_value=mock_cursor)

        result = await edition_repo.get_recent_processed_editions(days=7)

        assert len(result) == 2
        assert result[0]["edition_key"] == "2024-01-15_test1"

    @pytest.mark.asyncio
    async def test_get_recent_processed_editions_handles_error(self, edition_repo):
        """Database error - should return empty list."""
        edition_repo.collection.find = MagicMock(side_effect=Exception("DB error"))

        result = await edition_repo.get_recent_processed_editions(days=7)

        assert result == []


class TestRemoveAndCleanup:
    """Tests for remove_edition_from_tracking and cleanup_old_editions."""

    @pytest.mark.asyncio
    async def test_remove_edition_success(self, edition_repo):
        """Successfully remove edition from tracking."""
        mock_result = MagicMock()
        mock_result.deleted_count = 1
        edition_repo.collection.delete_one = AsyncMock(return_value=mock_result)

        result = await edition_repo.remove_edition_from_tracking("2024-01-15_test")

        assert result is True
        edition_repo.collection.delete_one.assert_called_once_with(
            {"edition_key": "2024-01-15_test"}
        )

    @pytest.mark.asyncio
    async def test_remove_edition_not_found(self, edition_repo):
        """Edition not found - should return False."""
        mock_result = MagicMock()
        mock_result.deleted_count = 0
        edition_repo.collection.delete_one = AsyncMock(return_value=mock_result)

        result = await edition_repo.remove_edition_from_tracking("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_cleanup_old_editions(self, edition_repo):
        """Cleanup editions older than specified days."""
        mock_result = MagicMock()
        mock_result.deleted_count = 5
        edition_repo.collection.delete_many = AsyncMock(return_value=mock_result)

        await edition_repo.cleanup_old_editions(days_to_keep=30)

        edition_repo.collection.delete_many.assert_called_once()
        # Verify the query includes a date filter
        call_args = edition_repo.collection.delete_many.call_args
        assert "processed_at" in call_args[0][0]
        assert "$lt" in call_args[0][0]["processed_at"]

    @pytest.mark.asyncio
    async def test_cleanup_handles_database_error(self, edition_repo):
        """Cleanup handles database errors gracefully."""
        edition_repo.collection.delete_many = AsyncMock(
            side_effect=Exception("DB error")
        )

        # Should not raise exception
        await edition_repo.cleanup_old_editions(days_to_keep=30)
