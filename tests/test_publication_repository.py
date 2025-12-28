"""Unit tests for PublicationRepository."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from depotbutler.db.repositories.publication import PublicationRepository


@pytest.fixture
def publication_repo():
    """Mock PublicationRepository with AsyncMock collection."""
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_collection = AsyncMock()

    # Mock the publications collection
    mock_db.publications = mock_collection
    mock_client.__getitem__ = MagicMock(return_value=mock_db)

    repo = PublicationRepository(client=mock_client, db_name="test_db")
    return repo


@pytest.fixture
def sample_publication():
    """Sample publication document."""
    return {
        "publication_id": "test_pub_001",
        "title": "Test Publication",
        "type": "magazine",
        "active": True,
        "email_enabled": True,
        "onedrive_enabled": True,
        "default_onedrive_folder": "Publications/Test",
        "created_at": datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
        "updated_at": datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
    }


class TestGetPublications:
    """Tests for get_publications method."""

    @pytest.mark.asyncio
    async def test_get_active_publications_only(
        self, publication_repo, sample_publication
    ):
        """Get only active publications (default behavior)."""

        # Create an async generator mock
        async def mock_async_generator():
            yield sample_publication

        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: mock_async_generator().__aiter__()
        publication_repo.collection.find = MagicMock(return_value=mock_cursor)

        result = await publication_repo.get_publications(active_only=True)

        assert len(result) == 1
        assert result[0]["publication_id"] == "test_pub_001"
        publication_repo.collection.find.assert_called_once_with({"active": True})

    @pytest.mark.asyncio
    async def test_get_all_publications_including_inactive(self, publication_repo):
        """Get all publications including inactive ones."""
        active_pub = {"publication_id": "active", "active": True}
        inactive_pub = {"publication_id": "inactive", "active": False}

        # Create an async generator mock
        async def mock_async_generator():
            yield active_pub
            yield inactive_pub

        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: mock_async_generator().__aiter__()
        publication_repo.collection.find = MagicMock(return_value=mock_cursor)

        result = await publication_repo.get_publications(active_only=False)

        assert len(result) == 2
        publication_repo.collection.find.assert_called_once_with({})

    @pytest.mark.asyncio
    async def test_get_publications_empty_result(self, publication_repo):
        """No publications found - returns empty list."""

        # Create an empty async generator
        async def mock_async_generator():
            return
            yield  # Make it a generator

        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: mock_async_generator().__aiter__()
        publication_repo.collection.find = MagicMock(return_value=mock_cursor)

        result = await publication_repo.get_publications()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_publications_handles_error(self, publication_repo):
        """Database error - returns empty list."""
        publication_repo.collection.find = MagicMock(side_effect=Exception("DB error"))

        result = await publication_repo.get_publications()

        assert result == []


class TestGetPublication:
    """Tests for get_publication method."""

    @pytest.mark.asyncio
    async def test_get_publication_success(self, publication_repo, sample_publication):
        """Successfully retrieve a publication by ID."""
        publication_repo.collection.find_one = AsyncMock(
            return_value=sample_publication
        )

        result = await publication_repo.get_publication("test_pub_001")

        assert result is not None
        assert result["publication_id"] == "test_pub_001"
        assert result["title"] == "Test Publication"
        publication_repo.collection.find_one.assert_called_once_with(
            {"publication_id": "test_pub_001"}
        )

    @pytest.mark.asyncio
    async def test_get_publication_not_found(self, publication_repo):
        """Publication not found - returns None."""
        publication_repo.collection.find_one = AsyncMock(return_value=None)

        result = await publication_repo.get_publication("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_publication_handles_error(self, publication_repo):
        """Database error - returns None."""
        publication_repo.collection.find_one = AsyncMock(
            side_effect=Exception("DB error")
        )

        result = await publication_repo.get_publication("test_pub_001")

        assert result is None


class TestCreatePublication:
    """Tests for create_publication method."""

    @pytest.mark.asyncio
    async def test_create_publication_success(
        self, publication_repo, sample_publication
    ):
        """Successfully create a new publication."""
        mock_result = MagicMock()
        mock_result.inserted_id = "mock_object_id"
        publication_repo.collection.insert_one = AsyncMock(return_value=mock_result)

        result = await publication_repo.create_publication(sample_publication.copy())

        assert result is True
        publication_repo.collection.insert_one.assert_called_once()

        # Verify timestamps were added
        call_args = publication_repo.collection.insert_one.call_args
        inserted_doc = call_args[0][0]
        assert "created_at" in inserted_doc
        assert "updated_at" in inserted_doc

    @pytest.mark.asyncio
    async def test_create_publication_adds_timestamps(self, publication_repo):
        """Create publication adds created_at and updated_at timestamps."""
        mock_result = MagicMock()
        mock_result.inserted_id = "mock_object_id"
        publication_repo.collection.insert_one = AsyncMock(return_value=mock_result)

        pub_data = {"publication_id": "test", "title": "Test"}
        result = await publication_repo.create_publication(pub_data)

        assert result is True
        call_args = publication_repo.collection.insert_one.call_args
        inserted_doc = call_args[0][0]

        assert isinstance(inserted_doc["created_at"], datetime)
        assert isinstance(inserted_doc["updated_at"], datetime)
        assert inserted_doc["created_at"] == inserted_doc["updated_at"]

    @pytest.mark.asyncio
    async def test_create_publication_handles_error(
        self, publication_repo, sample_publication
    ):
        """Database error - returns False."""
        publication_repo.collection.insert_one = AsyncMock(
            side_effect=Exception("DB error")
        )

        result = await publication_repo.create_publication(sample_publication)

        assert result is False


class TestUpdatePublication:
    """Tests for update_publication method."""

    @pytest.mark.asyncio
    async def test_update_publication_success(self, publication_repo):
        """Successfully update a publication."""
        mock_result = MagicMock()
        mock_result.modified_count = 1
        publication_repo.collection.update_one = AsyncMock(return_value=mock_result)

        updates = {"title": "Updated Title", "active": False}
        result = await publication_repo.update_publication("test_pub_001", updates)

        assert result is True
        publication_repo.collection.update_one.assert_called_once()

        # Verify update_one was called with correct structure
        call_args = publication_repo.collection.update_one.call_args
        assert call_args[0][0] == {"publication_id": "test_pub_001"}
        assert "$set" in call_args[0][1]

        # Verify updated_at was added
        update_doc = call_args[0][1]["$set"]
        assert "updated_at" in update_doc
        assert isinstance(update_doc["updated_at"], datetime)

    @pytest.mark.asyncio
    async def test_update_publication_not_found(self, publication_repo):
        """Publication not found - returns False."""
        mock_result = MagicMock()
        mock_result.modified_count = 0
        publication_repo.collection.update_one = AsyncMock(return_value=mock_result)

        updates = {"title": "Updated Title"}
        result = await publication_repo.update_publication("nonexistent", updates)

        assert result is False

    @pytest.mark.asyncio
    async def test_update_publication_adds_timestamp(self, publication_repo):
        """Update automatically adds updated_at timestamp."""
        mock_result = MagicMock()
        mock_result.modified_count = 1
        publication_repo.collection.update_one = AsyncMock(return_value=mock_result)

        updates = {"email_enabled": False}
        result = await publication_repo.update_publication("test_pub_001", updates)

        assert result is True
        call_args = publication_repo.collection.update_one.call_args
        update_doc = call_args[0][1]["$set"]

        assert "email_enabled" in update_doc
        assert "updated_at" in update_doc
        assert update_doc["email_enabled"] is False

    @pytest.mark.asyncio
    async def test_update_publication_handles_error(self, publication_repo):
        """Database error - returns False."""
        publication_repo.collection.update_one = AsyncMock(
            side_effect=Exception("DB error")
        )

        updates = {"title": "Updated Title"}
        result = await publication_repo.update_publication("test_pub_001", updates)

        assert result is False
