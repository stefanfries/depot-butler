"""Tests for EditionTrackingService (edition_tracker.py)."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from depotbutler.models import Edition, ProcessedEdition
from depotbutler.services.edition_tracking_service import EditionTrackingService


@pytest.fixture
def mock_mongodb():
    """Create mock MongoDB service."""
    mongodb = MagicMock()
    mongodb.is_edition_processed = AsyncMock(return_value=False)
    mongodb.mark_edition_processed = AsyncMock(return_value=True)
    mongodb.get_processed_editions_count = AsyncMock(return_value=10)
    mongodb.get_recent_processed_editions = AsyncMock(return_value=[])
    mongodb.remove_edition_from_tracking = AsyncMock(return_value=True)
    mongodb.cleanup_old_editions = AsyncMock()
    return mongodb


@pytest.fixture
def edition_tracker(mock_mongodb):
    """Create EditionTrackingService instance."""
    return EditionTrackingService(mongodb=mock_mongodb, retention_days=90)


@pytest.fixture
def mock_edition():
    """Create mock Edition."""
    return Edition(
        title="Test Magazine 47/2025",
        publication_date="2025-11-23",
        details_url="https://example.com/details",
        download_url="https://example.com/download.pdf",
    )


def test_edition_tracker_initialization(mock_mongodb):
    """Test EditionTrackingService initialization."""
    tracker = EditionTrackingService(mongodb=mock_mongodb, retention_days=60)

    assert tracker.mongodb == mock_mongodb
    assert tracker.retention_days == 60


def test_generate_edition_key(edition_tracker, mock_edition):
    """Test edition key generation."""
    key = edition_tracker._generate_edition_key(mock_edition)

    assert key == "2025-11-23_Test Magazine 47/2025"
    assert isinstance(key, str)


@pytest.mark.asyncio
async def test_is_already_processed_true(edition_tracker, mock_edition, mock_mongodb):
    """Test checking if edition is already processed (returns True)."""
    mock_mongodb.is_edition_processed.return_value = True

    result = await edition_tracker.is_already_processed(mock_edition)

    assert result is True
    mock_mongodb.is_edition_processed.assert_called_once_with(
        "2025-11-23_Test Magazine 47/2025"
    )


@pytest.mark.asyncio
async def test_is_already_processed_false(edition_tracker, mock_edition, mock_mongodb):
    """Test checking if edition is not processed (returns False)."""
    mock_mongodb.is_edition_processed.return_value = False

    result = await edition_tracker.is_already_processed(mock_edition)

    assert result is False
    mock_mongodb.is_edition_processed.assert_called_once()


@pytest.mark.asyncio
async def test_mark_as_processed_success(edition_tracker, mock_edition, mock_mongodb):
    """Test marking edition as processed successfully."""
    mock_mongodb.mark_edition_processed.return_value = True

    await edition_tracker.mark_as_processed(mock_edition, file_path="/path/to/file.pdf")

    mock_mongodb.mark_edition_processed.assert_called_once_with(
        edition_key="2025-11-23_Test Magazine 47/2025",
        title="Test Magazine 47/2025",
        publication_date="2025-11-23",
        download_url="https://example.com/download.pdf",
        file_path="/path/to/file.pdf",
    )


@pytest.mark.asyncio
async def test_mark_as_processed_no_file_path(
    edition_tracker, mock_edition, mock_mongodb
):
    """Test marking edition as processed without file path."""
    mock_mongodb.mark_edition_processed.return_value = True

    await edition_tracker.mark_as_processed(mock_edition)

    mock_mongodb.mark_edition_processed.assert_called_once()
    call_args = mock_mongodb.mark_edition_processed.call_args[1]
    assert call_args["file_path"] == ""


@pytest.mark.asyncio
async def test_mark_as_processed_failure(edition_tracker, mock_edition, mock_mongodb):
    """Test handling failure when marking edition as processed."""
    mock_mongodb.mark_edition_processed.return_value = False

    # Should not raise exception, just log warning
    await edition_tracker.mark_as_processed(mock_edition)

    mock_mongodb.mark_edition_processed.assert_called_once()


@pytest.mark.asyncio
async def test_get_processed_count(edition_tracker, mock_mongodb):
    """Test getting count of processed editions."""
    mock_mongodb.get_processed_editions_count.return_value = 42

    count = await edition_tracker.get_processed_count()

    assert count == 42
    mock_mongodb.get_processed_editions_count.assert_called_once()


@pytest.mark.asyncio
async def test_get_recent_editions_empty(edition_tracker, mock_mongodb):
    """Test getting recent editions when none exist."""
    mock_mongodb.get_recent_processed_editions.return_value = []

    editions = await edition_tracker.get_recent_editions(days=30)

    assert editions == []
    mock_mongodb.get_recent_processed_editions.assert_called_once_with(30)


@pytest.mark.asyncio
async def test_get_recent_editions_with_data(edition_tracker, mock_mongodb):
    """Test getting recent editions with data."""
    mock_data = [
        {
            "title": "Magazine 46/2025",
            "publication_date": "2025-11-16",
            "download_url": "https://example.com/46.pdf",
            "processed_at": datetime(2025, 11, 16, 10, 30),
            "file_path": "/path/to/46.pdf",
        },
        {
            "title": "Magazine 47/2025",
            "publication_date": "2025-11-23",
            "download_url": "https://example.com/47.pdf",
            "processed_at": datetime(2025, 11, 23, 14, 15),
            "file_path": "/path/to/47.pdf",
        },
    ]
    mock_mongodb.get_recent_processed_editions.return_value = mock_data

    editions = await edition_tracker.get_recent_editions(days=7)

    assert len(editions) == 2
    assert all(isinstance(e, ProcessedEdition) for e in editions)
    assert editions[0].title == "Magazine 46/2025"
    assert editions[0].publication_date == "2025-11-16"
    assert editions[0].file_path == "/path/to/46.pdf"
    assert editions[1].title == "Magazine 47/2025"
    mock_mongodb.get_recent_processed_editions.assert_called_once_with(7)


@pytest.mark.asyncio
async def test_get_recent_editions_no_file_path(edition_tracker, mock_mongodb):
    """Test getting recent editions when file_path is missing."""
    mock_data = [
        {
            "title": "Magazine 46/2025",
            "publication_date": "2025-11-16",
            "download_url": "https://example.com/46.pdf",
            "processed_at": datetime(2025, 11, 16, 10, 30),
            # No file_path
        },
    ]
    mock_mongodb.get_recent_processed_editions.return_value = mock_data

    editions = await edition_tracker.get_recent_editions()

    assert len(editions) == 1
    assert editions[0].file_path == ""


@pytest.mark.asyncio
async def test_force_reprocess_success(edition_tracker, mock_edition, mock_mongodb):
    """Test forcing reprocess successfully."""
    mock_mongodb.remove_edition_from_tracking.return_value = True

    result = await edition_tracker.force_reprocess(mock_edition)

    assert result is True
    mock_mongodb.remove_edition_from_tracking.assert_called_once_with(
        "2025-11-23_Test Magazine 47/2025"
    )


@pytest.mark.asyncio
async def test_force_reprocess_not_tracked(edition_tracker, mock_edition, mock_mongodb):
    """Test forcing reprocess when edition wasn't tracked."""
    mock_mongodb.remove_edition_from_tracking.return_value = False

    result = await edition_tracker.force_reprocess(mock_edition)

    assert result is False
    mock_mongodb.remove_edition_from_tracking.assert_called_once()


@pytest.mark.asyncio
async def test_cleanup_old_entries(edition_tracker, mock_mongodb):
    """Test cleaning up old entries."""
    await edition_tracker.cleanup_old_entries()

    mock_mongodb.cleanup_old_editions.assert_called_once_with(90)


@pytest.mark.asyncio
async def test_cleanup_old_entries_custom_retention(mock_mongodb):
    """Test cleanup with custom retention period."""
    tracker = EditionTrackingService(mongodb=mock_mongodb, retention_days=30)

    await tracker.cleanup_old_entries()

    mock_mongodb.cleanup_old_editions.assert_called_once_with(30)


def test_processed_edition_pydantic_model():
    """Test ProcessedEdition Pydantic model creation."""
    edition = ProcessedEdition(
        title="Test Magazine",
        publication_date="2025-11-23",
        download_url="https://example.com/test.pdf",
        processed_at=datetime(2025, 11, 23, 10, 30),
        file_path="/path/to/test.pdf",
    )

    assert edition.title == "Test Magazine"
    assert edition.publication_date == "2025-11-23"
    assert edition.download_url == "https://example.com/test.pdf"
    assert edition.processed_at == datetime(2025, 11, 23, 10, 30)
    assert edition.file_path == "/path/to/test.pdf"

    # Verify Pydantic model behavior
    assert hasattr(edition, "model_dump")
    data = edition.model_dump()
    assert data["title"] == "Test Magazine"


def test_processed_edition_default_file_path():
    """Test ProcessedEdition with default file_path."""
    edition = ProcessedEdition(
        title="Test Magazine",
        publication_date="2025-11-23",
        download_url="https://example.com/test.pdf",
        processed_at=datetime(2025, 11, 23, 10, 30),
    )

    assert edition.file_path == ""
