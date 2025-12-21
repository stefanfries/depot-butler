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

    mock_client = MagicMock()
    mock_client.admin.command = AsyncMock(
        side_effect=ConnectionFailure("Connection failed")
    )

    with patch("depotbutler.db.mongodb.AsyncIOMotorClient", return_value=mock_client):
        with pytest.raises(ConnectionFailure):
            await mongodb_service.connect()


@pytest.mark.asyncio
async def test_close_connection(mongodb_service):
    """Test closing MongoDB connection."""
    mock_client = (
        MagicMock()
    )  # Use MagicMock instead of AsyncMock since close() is not async
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
    # Make close() a regular method, not async
    mock_client.close = MagicMock()

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


@pytest.mark.asyncio
async def test_get_auth_cookie_success(mongodb_service):
    """Test successful retrieval of auth cookie from MongoDB."""
    mock_client = AsyncMock()
    mock_client.admin.command = AsyncMock(return_value={"ok": 1})

    mock_collection = AsyncMock()
    mock_collection.find_one = AsyncMock(
        return_value={
            "_id": "auth_cookie",
            "cookie_value": "test_cookie_value_12345",
            "updated_at": datetime.now(timezone.utc),
            "updated_by": "test_user",
        }
    )

    mock_db = MagicMock()
    mock_db.config = mock_collection

    with patch("depotbutler.db.mongodb.AsyncIOMotorClient", return_value=mock_client):
        mongodb_service.db = mock_db
        mongodb_service._connected = True

        cookie_value = await mongodb_service.get_auth_cookie()

        assert cookie_value == "test_cookie_value_12345"
        mock_collection.find_one.assert_called_once_with({"_id": "auth_cookie"})


@pytest.mark.asyncio
async def test_get_auth_cookie_not_found(mongodb_service):
    """Test auth cookie retrieval when not found in MongoDB."""
    mock_client = AsyncMock()
    mock_client.admin.command = AsyncMock(return_value={"ok": 1})

    mock_collection = AsyncMock()
    mock_collection.find_one = AsyncMock(return_value=None)

    mock_db = MagicMock()
    mock_db.config = mock_collection

    with patch("depotbutler.db.mongodb.AsyncIOMotorClient", return_value=mock_client):
        mongodb_service.db = mock_db
        mongodb_service._connected = True

        cookie_value = await mongodb_service.get_auth_cookie()

        assert cookie_value is None
        mock_collection.find_one.assert_called_once_with({"_id": "auth_cookie"})


@pytest.mark.asyncio
async def test_update_auth_cookie_success(mongodb_service):
    """Test successful update of auth cookie in MongoDB."""
    mock_client = AsyncMock()
    mock_client.admin.command = AsyncMock(return_value={"ok": 1})

    mock_result = MagicMock()
    mock_result.modified_count = 1
    mock_result.upserted_id = None

    mock_collection = AsyncMock()
    mock_collection.update_one = AsyncMock(return_value=mock_result)

    mock_db = MagicMock()
    mock_db.config = mock_collection

    with patch("depotbutler.db.mongodb.AsyncIOMotorClient", return_value=mock_client):
        mongodb_service.db = mock_db
        mongodb_service._connected = True

        success = await mongodb_service.update_auth_cookie(
            "new_cookie_value", "test_user"
        )

        assert success is True
        mock_collection.update_one.assert_called_once()


@pytest.mark.asyncio
async def test_update_auth_cookie_upsert(mongodb_service):
    """Test upserting new auth cookie in MongoDB."""
    mock_client = AsyncMock()
    mock_client.admin.command = AsyncMock(return_value={"ok": 1})

    mock_result = MagicMock()
    mock_result.modified_count = 0
    mock_result.upserted_id = "auth_cookie"

    mock_collection = AsyncMock()
    mock_collection.update_one = AsyncMock(return_value=mock_result)

    mock_db = MagicMock()
    mock_db.config = mock_collection

    with patch("depotbutler.db.mongodb.AsyncIOMotorClient", return_value=mock_client):
        mongodb_service.db = mock_db
        mongodb_service._connected = True

        success = await mongodb_service.update_auth_cookie(
            "new_cookie_value", "test_user"
        )

        assert success is True
        mock_collection.update_one.assert_called_once()


# ==================== Publications Tests ====================


@pytest.mark.asyncio
async def test_get_publications_success(mongodb_service):
    """Test retrieving all active publications."""
    mock_client = AsyncMock()
    mock_client.admin.command = AsyncMock(return_value={"ok": 1})

    mock_publications = [
        {
            "publication_id": "pub1",
            "name": "Test Publication 1",
            "active": True,
            "email_enabled": True,
        },
        {
            "publication_id": "pub2",
            "name": "Test Publication 2",
            "active": True,
            "email_enabled": False,
        },
    ]

    mock_cursor = AsyncMock()
    mock_cursor.__aiter__.return_value = iter(mock_publications)

    mock_collection = MagicMock()
    mock_collection.find = MagicMock(return_value=mock_cursor)

    mock_db = MagicMock()
    mock_db.publications = mock_collection

    with patch("depotbutler.db.mongodb.AsyncIOMotorClient", return_value=mock_client):
        mongodb_service.db = mock_db
        mongodb_service._connected = True

        publications = await mongodb_service.get_publications()

        assert len(publications) == 2
        assert publications[0]["publication_id"] == "pub1"
        assert publications[1]["publication_id"] == "pub2"
        mock_collection.find.assert_called_once_with({"active": True})


@pytest.mark.asyncio
async def test_get_publications_all(mongodb_service):
    """Test retrieving all publications including inactive."""
    mock_client = AsyncMock()
    mock_client.admin.command = AsyncMock(return_value={"ok": 1})

    mock_publications = [
        {"publication_id": "pub1", "active": True},
        {"publication_id": "pub2", "active": False},
    ]

    mock_cursor = AsyncMock()
    mock_cursor.__aiter__.return_value = iter(mock_publications)

    mock_collection = MagicMock()
    mock_collection.find = MagicMock(return_value=mock_cursor)

    mock_db = MagicMock()
    mock_db.publications = mock_collection

    with patch("depotbutler.db.mongodb.AsyncIOMotorClient", return_value=mock_client):
        mongodb_service.db = mock_db
        mongodb_service._connected = True

        publications = await mongodb_service.get_publications(active_only=False)

        assert len(publications) == 2
        mock_collection.find.assert_called_once_with({})


@pytest.mark.asyncio
async def test_get_publication_found(mongodb_service):
    """Test retrieving a single publication by ID."""
    mock_client = AsyncMock()
    mock_client.admin.command = AsyncMock(return_value={"ok": 1})

    mock_publication = {
        "publication_id": "test-pub",
        "name": "Test Publication",
        "active": True,
    }

    mock_collection = AsyncMock()
    mock_collection.find_one = AsyncMock(return_value=mock_publication)

    mock_db = MagicMock()
    mock_db.publications = mock_collection

    with patch("depotbutler.db.mongodb.AsyncIOMotorClient", return_value=mock_client):
        mongodb_service.db = mock_db
        mongodb_service._connected = True

        publication = await mongodb_service.get_publication("test-pub")

        assert publication is not None
        assert publication["publication_id"] == "test-pub"
        mock_collection.find_one.assert_called_once_with({"publication_id": "test-pub"})


@pytest.mark.asyncio
async def test_get_publication_not_found(mongodb_service):
    """Test retrieving non-existent publication."""
    mock_client = AsyncMock()
    mock_client.admin.command = AsyncMock(return_value={"ok": 1})

    mock_collection = AsyncMock()
    mock_collection.find_one = AsyncMock(return_value=None)

    mock_db = MagicMock()
    mock_db.publications = mock_collection

    with patch("depotbutler.db.mongodb.AsyncIOMotorClient", return_value=mock_client):
        mongodb_service.db = mock_db
        mongodb_service._connected = True

        publication = await mongodb_service.get_publication("nonexistent")

        assert publication is None


@pytest.mark.asyncio
async def test_create_publication_success(mongodb_service):
    """Test creating a new publication."""
    mock_client = AsyncMock()
    mock_client.admin.command = AsyncMock(return_value={"ok": 1})

    mock_result = MagicMock()
    mock_result.inserted_id = "507f1f77bcf86cd799439011"

    mock_collection = AsyncMock()
    mock_collection.insert_one = AsyncMock(return_value=mock_result)

    mock_db = MagicMock()
    mock_db.publications = mock_collection

    publication_data = {
        "publication_id": "new-pub",
        "name": "New Publication",
        "active": True,
        "email_enabled": True,
    }

    with patch("depotbutler.db.mongodb.AsyncIOMotorClient", return_value=mock_client):
        mongodb_service.db = mock_db
        mongodb_service._connected = True

        success = await mongodb_service.create_publication(publication_data)

        assert success is True
        mock_collection.insert_one.assert_called_once()
        # Verify timestamps were added
        call_args = mock_collection.insert_one.call_args[0][0]
        assert "created_at" in call_args
        assert "updated_at" in call_args


@pytest.mark.asyncio
async def test_update_publication_success(mongodb_service):
    """Test updating an existing publication."""
    mock_client = AsyncMock()
    mock_client.admin.command = AsyncMock(return_value={"ok": 1})

    mock_result = MagicMock()
    mock_result.modified_count = 1

    mock_collection = AsyncMock()
    mock_collection.update_one = AsyncMock(return_value=mock_result)

    mock_db = MagicMock()
    mock_db.publications = mock_collection

    updates = {"email_enabled": False, "onedrive_enabled": True}

    with patch("depotbutler.db.mongodb.AsyncIOMotorClient", return_value=mock_client):
        mongodb_service.db = mock_db
        mongodb_service._connected = True

        success = await mongodb_service.update_publication("test-pub", updates)

        assert success is True
        mock_collection.update_one.assert_called_once()
        # Verify update timestamp was added
        call_args = mock_collection.update_one.call_args[0]
        assert "updated_at" in call_args[1]["$set"]


@pytest.mark.asyncio
async def test_update_publication_not_found(mongodb_service):
    """Test updating non-existent publication."""
    mock_client = AsyncMock()
    mock_client.admin.command = AsyncMock(return_value={"ok": 1})

    mock_result = MagicMock()
    mock_result.modified_count = 0

    mock_collection = AsyncMock()
    mock_collection.update_one = AsyncMock(return_value=mock_result)

    mock_db = MagicMock()
    mock_db.publications = mock_collection

    updates = {"email_enabled": False}

    with patch("depotbutler.db.mongodb.AsyncIOMotorClient", return_value=mock_client):
        mongodb_service.db = mock_db
        mongodb_service._connected = True

        success = await mongodb_service.update_publication("nonexistent", updates)

        assert success is False


@pytest.mark.asyncio
async def test_get_cookie_expiration_info_success(mongodb_service):
    """Test successful retrieval of cookie expiration info."""
    from datetime import timedelta

    expiration_date = datetime.now(timezone.utc) + timedelta(days=10)

    mock_collection = AsyncMock()
    mock_collection.find_one = AsyncMock(
        return_value={
            "_id": "auth_cookie",
            "cookie_value": "test_cookie",
            "expires_at": expiration_date,
            "updated_at": datetime.now(timezone.utc),
        }
    )

    mock_db = MagicMock()
    mock_db.config = mock_collection

    mongodb_service.db = mock_db
    mongodb_service._connected = True

    info = await mongodb_service.get_cookie_expiration_info()

    assert info is not None
    assert "expires_at" in info
    assert "days_remaining" in info
    assert info["days_remaining"] >= 9  # Should be around 10 days
    assert info["is_expired"] is False


@pytest.mark.asyncio
async def test_get_cookie_expiration_info_expired(mongodb_service):
    """Test cookie expiration info when cookie is expired."""
    from datetime import timedelta

    expiration_date = datetime.now(timezone.utc) - timedelta(days=5)

    mock_collection = AsyncMock()
    mock_collection.find_one = AsyncMock(
        return_value={
            "_id": "auth_cookie",
            "cookie_value": "test_cookie",
            "expires_at": expiration_date,
            "updated_at": datetime.now(timezone.utc),
        }
    )

    mock_db = MagicMock()
    mock_db.config = mock_collection

    mongodb_service.db = mock_db
    mongodb_service._connected = True

    info = await mongodb_service.get_cookie_expiration_info()

    assert info is not None
    assert info["is_expired"] is True
    assert info["days_remaining"] < 0


@pytest.mark.asyncio
async def test_get_cookie_expiration_info_no_expiration(mongodb_service):
    """Test cookie expiration info when no expiration date set."""
    mock_collection = AsyncMock()
    mock_collection.find_one = AsyncMock(
        return_value={
            "_id": "auth_cookie",
            "cookie_value": "test_cookie",
            "updated_at": datetime.now(timezone.utc),
            # No expires_at field
        }
    )

    mock_db = MagicMock()
    mock_db.config = mock_collection

    mongodb_service.db = mock_db
    mongodb_service._connected = True

    info = await mongodb_service.get_cookie_expiration_info()

    # Returns dict with warning when no expiration date
    assert info is not None
    assert info["warning"] == "No expiration date stored"
    assert info["expires_at"] is None
    assert info["days_remaining"] is None
    assert info["is_expired"] is None


@pytest.mark.asyncio
async def test_get_cookie_expiration_info_not_found(mongodb_service):
    """Test cookie expiration info when cookie not found."""
    mock_collection = AsyncMock()
    mock_collection.find_one = AsyncMock(return_value=None)

    mock_db = MagicMock()
    mock_db.config = mock_collection

    mongodb_service.db = mock_db
    mongodb_service._connected = True

    info = await mongodb_service.get_cookie_expiration_info()

    assert info is None


@pytest.mark.asyncio
async def test_get_app_config_success(mongodb_service):
    """Test successful retrieval of app config value."""
    mock_collection = AsyncMock()
    # Mock the nested structure for app_config
    mock_collection.find_one = AsyncMock(
        return_value={"_id": "app_config", "test_config": "test_value"}
    )

    mock_db = MagicMock()
    mock_db.config = mock_collection

    mongodb_service.db = mock_db
    mongodb_service._connected = True

    value = await mongodb_service.get_app_config("test_config")

    assert value == "test_value"


@pytest.mark.asyncio
async def test_get_app_config_with_default(mongodb_service):
    """Test get_app_config returns default when not found."""
    mock_collection = AsyncMock()
    mock_collection.find_one = AsyncMock(return_value=None)

    mock_db = MagicMock()
    mock_db.config = mock_collection

    mongodb_service.db = mock_db
    mongodb_service._connected = True

    value = await mongodb_service.get_app_config("nonexistent", default="default_value")

    assert value == "default_value"


@pytest.mark.asyncio
async def test_get_app_config_no_default(mongodb_service):
    """Test get_app_config returns None when not found and no default."""
    mock_collection = AsyncMock()
    mock_collection.find_one = AsyncMock(return_value=None)

    mock_db = MagicMock()
    mock_db.config = mock_collection

    mongodb_service.db = mock_db
    mongodb_service._connected = True

    value = await mongodb_service.get_app_config("nonexistent")

    assert value is None


@pytest.mark.asyncio
async def test_get_active_recipients_function():
    """Test standalone get_active_recipients function."""
    mock_service = AsyncMock()
    mock_service.get_active_recipients = AsyncMock(
        return_value=[{"email": "test@example.com", "first_name": "Test"}]
    )

    with patch("depotbutler.db.mongodb.get_mongodb_service", return_value=mock_service):
        recipients = await get_active_recipients()

        assert len(recipients) == 1
        assert recipients[0]["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_update_recipient_stats_function():
    """Test standalone update_recipient_stats function."""
    mock_service = AsyncMock()
    mock_service.update_recipient_stats = AsyncMock()

    with patch("depotbutler.db.mongodb.get_mongodb_service", return_value=mock_service):
        await update_recipient_stats("test@example.com")

        # Note: publication_id defaults to None for backward compatibility
        mock_service.update_recipient_stats.assert_called_once_with(
            "test@example.com", None
        )


@pytest.mark.asyncio
async def test_get_publications_exception_handling(mongodb_service):
    """Test get_publications handles exceptions."""
    mock_collection = AsyncMock()
    mock_collection.find = MagicMock(side_effect=Exception("Database error"))

    mock_db = MagicMock()
    mock_db.publications = mock_collection

    mongodb_service.db = mock_db
    mongodb_service._connected = True

    # Should return empty list on error
    publications = await mongodb_service.get_publications()

    assert publications == []


@pytest.mark.asyncio
async def test_get_publication_exception_handling(mongodb_service):
    """Test get_publication handles exceptions."""
    mock_collection = AsyncMock()
    mock_collection.find_one = AsyncMock(side_effect=Exception("Database error"))

    mock_db = MagicMock()
    mock_db.publications = mock_collection

    mongodb_service.db = mock_db
    mongodb_service._connected = True

    # Should return None on error
    publication = await mongodb_service.get_publication("test-pub")

    assert publication is None


@pytest.mark.asyncio
async def test_create_publication_exception_handling(mongodb_service):
    """Test create_publication handles exceptions."""
    mock_collection = AsyncMock()
    mock_collection.insert_one = AsyncMock(side_effect=Exception("Insert error"))

    mock_db = MagicMock()
    mock_db.publications = mock_collection

    mongodb_service.db = mock_db
    mongodb_service._connected = True

    pub_data = {"publication_id": "test-pub", "name": "Test"}

    # Should return False on error
    success = await mongodb_service.create_publication(pub_data)

    assert success is False


@pytest.mark.asyncio
async def test_update_publication_exception_handling(mongodb_service):
    """Test update_publication handles exceptions."""
    mock_collection = AsyncMock()
    mock_collection.update_one = AsyncMock(side_effect=Exception("Update error"))

    mock_db = MagicMock()
    mock_db.publications = mock_collection

    mongodb_service.db = mock_db
    mongodb_service._connected = True

    # Should return False on error
    success = await mongodb_service.update_publication("test-pub", {"name": "Updated"})

    assert success is False


@pytest.mark.asyncio
async def test_get_active_recipients_exception_handling(mongodb_service):
    """Test get_active_recipients handles exceptions."""
    mock_collection = MagicMock()
    mock_collection.find = MagicMock(side_effect=Exception("Query error"))

    mock_db = MagicMock()
    mock_db.recipients = mock_collection

    mongodb_service.db = mock_db
    mongodb_service._connected = True

    # Should return empty list on error
    recipients = await mongodb_service.get_active_recipients()

    assert recipients == []


@pytest.mark.asyncio
async def test_update_recipient_stats_exception_handling(mongodb_service):
    """Test update_recipient_stats handles exceptions."""
    mock_collection = AsyncMock()
    mock_collection.update_one = AsyncMock(side_effect=Exception("Update error"))

    mock_db = MagicMock()
    mock_db.recipients = mock_collection

    mongodb_service.db = mock_db
    mongodb_service._connected = True

    # Should not raise exception
    await mongodb_service.update_recipient_stats("test@example.com")
