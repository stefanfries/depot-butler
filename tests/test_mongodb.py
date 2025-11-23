"""Tests for MongoDB service layer."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from depotbutler.db.mongodb import (
    MongoDBService,
    get_active_recipients,
    update_recipient_stats,
)


@pytest.fixture
def mock_settings():
    """Mock Settings object."""
    settings = MagicMock()
    settings.mongodb.name = "test_db"
    settings.mongodb.connection_string = "mongodb://localhost:27017"
    return settings


@pytest.fixture
def mongodb_service(mock_settings):
    """Create MongoDBService instance with mocked settings."""
    with patch("depotbutler.db.mongodb.Settings", return_value=mock_settings):
        service = MongoDBService()
        return service


@pytest.mark.asyncio
async def test_connect_success(mongodb_service):
    """Test successful MongoDB connection."""
    mock_client = AsyncMock()
    mock_client.admin.command = AsyncMock(return_value={"ok": 1})

    with patch("depotbutler.db.mongodb.AsyncIOMotorClient", return_value=mock_client):
        await mongodb_service.connect()

        assert mongodb_service._connected is True
        assert mongodb_service.client is not None
        assert mongodb_service.db is not None
        mock_client.admin.command.assert_called_once_with("ping")


@pytest.mark.asyncio
async def test_connect_failure(mongodb_service):
    """Test connection failure handling."""
    from pymongo.errors import ConnectionFailure

    mock_client = AsyncMock()
    mock_client.admin.command = AsyncMock(
        side_effect=ConnectionFailure("Connection failed")
    )

    with patch("depotbutler.db.mongodb.AsyncIOMotorClient", return_value=mock_client):
        with pytest.raises(ConnectionFailure):
            await mongodb_service.connect()


@pytest.mark.asyncio
async def test_close_connection(mongodb_service):
    """Test closing MongoDB connection."""
    mock_client = AsyncMock()
    mongodb_service.client = mock_client
    mongodb_service._connected = True

    await mongodb_service.close()

    assert mongodb_service._connected is False
    mock_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_get_active_recipients_success(mongodb_service):
    """Test fetching active recipients successfully."""
    mock_recipients = [
        {
            "email": "test1@example.com",
            "first_name": "Test",
            "last_name": "User1",
            "recipient_type": "regular",
        },
        {
            "email": "test2@example.com",
            "first_name": "Test",
            "last_name": "User2",
            "recipient_type": "admin",
        },
    ]

    mock_cursor = AsyncMock()
    mock_cursor.to_list = AsyncMock(return_value=mock_recipients)
    mock_cursor.sort = MagicMock(return_value=mock_cursor)

    mock_collection = MagicMock()
    mock_collection.find = MagicMock(return_value=mock_cursor)

    mock_db = MagicMock()
    mock_db.recipients = mock_collection

    mongodb_service.db = mock_db
    mongodb_service._connected = True

    recipients = await mongodb_service.get_active_recipients()

    assert len(recipients) == 2
    assert recipients[0]["email"] == "test1@example.com"
    assert recipients[1]["email"] == "test2@example.com"
    mock_collection.find.assert_called_once()


@pytest.mark.asyncio
async def test_get_active_recipients_empty(mongodb_service):
    """Test fetching recipients when none exist."""
    mock_cursor = AsyncMock()
    mock_cursor.to_list = AsyncMock(return_value=[])
    mock_cursor.sort = MagicMock(return_value=mock_cursor)

    mock_collection = MagicMock()
    mock_collection.find = MagicMock(return_value=mock_cursor)

    mock_db = MagicMock()
    mock_db.recipients = mock_collection

    mongodb_service.db = mock_db
    mongodb_service._connected = True

    recipients = await mongodb_service.get_active_recipients()

    assert len(recipients) == 0


@pytest.mark.asyncio
async def test_update_recipient_stats_success(mongodb_service):
    """Test updating recipient statistics."""
    mock_result = MagicMock()
    mock_result.modified_count = 1

    mock_collection = AsyncMock()
    mock_collection.update_one = AsyncMock(return_value=mock_result)

    mock_db = MagicMock()
    mock_db.recipients = mock_collection

    mongodb_service.db = mock_db
    mongodb_service._connected = True

    await mongodb_service.update_recipient_stats("test@example.com")

    mock_collection.update_one.assert_called_once()
    call_args = mock_collection.update_one.call_args

    # Verify filter
    assert call_args[0][0] == {"email": "test@example.com"}

    # Verify update operations
    update_ops = call_args[0][1]
    assert "$set" in update_ops
    assert "$inc" in update_ops
    assert update_ops["$inc"]["send_count"] == 1


@pytest.mark.asyncio
async def test_update_recipient_stats_not_found(mongodb_service):
    """Test updating stats for non-existent recipient."""
    mock_result = MagicMock()
    mock_result.modified_count = 0

    mock_collection = AsyncMock()
    mock_collection.update_one = AsyncMock(return_value=mock_result)

    mock_db = MagicMock()
    mock_db.recipients = mock_collection

    mongodb_service.db = mock_db
    mongodb_service._connected = True

    # Should not raise exception, just log warning
    await mongodb_service.update_recipient_stats("nonexistent@example.com")

    mock_collection.update_one.assert_called_once()


@pytest.mark.asyncio
async def test_context_manager(mongodb_service):
    """Test MongoDB service as async context manager."""
    mock_client = AsyncMock()
    mock_client.admin.command = AsyncMock(return_value={"ok": 1})

    with patch("depotbutler.db.mongodb.AsyncIOMotorClient", return_value=mock_client):
        async with mongodb_service:
            assert mongodb_service._connected is True

        # After exiting context, connection should be closed
        assert mongodb_service._connected is False
        mock_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_auto_connect_on_query(mongodb_service):
    """Test that queries automatically connect if not connected."""
    mock_client = AsyncMock()
    mock_client.admin.command = AsyncMock(return_value={"ok": 1})

    mock_cursor = AsyncMock()
    mock_cursor.to_list = AsyncMock(return_value=[])
    mock_cursor.sort = MagicMock(return_value=mock_cursor)

    mock_collection = MagicMock()
    mock_collection.find = MagicMock(return_value=mock_cursor)

    mock_db = MagicMock()
    mock_db.recipients = mock_collection

    with patch("depotbutler.db.mongodb.AsyncIOMotorClient", return_value=mock_client):
        mongodb_service._connected = False

        # Mock db assignment during connect
        def setup_db(*args, **kwargs):
            mongodb_service.db = mock_db
            mongodb_service._connected = True

        mock_client.admin.command.side_effect = setup_db

        await mongodb_service.get_active_recipients()

        # Should have auto-connected
        mock_client.admin.command.assert_called_once()
