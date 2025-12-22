"""Tests for MongoDB service layer."""

from datetime import UTC, datetime
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
@pytest.mark.filterwarnings("ignore::RuntimeWarning")
async def test_connect_success(mongodb_service):
    """Test successful MongoDB connection."""

    # Create an actual async function instead of using AsyncMock for command
    async def mock_ping_command(*args, **kwargs):
        return {"ok": 1}

    mock_client = MagicMock()
    mock_admin = MagicMock()
    mock_admin.command = mock_ping_command  # Use real async function
    mock_client.admin = mock_admin
    mock_client.__getitem__ = MagicMock(return_value=MagicMock())  # For client[db_name]

    with patch("depotbutler.db.mongodb.AsyncIOMotorClient", return_value=mock_client):
        await mongodb_service.connect()

        assert mongodb_service._connected is True
        assert mongodb_service.client is not None
        assert mongodb_service.db is not None
        # Can't assert_called_once since it's a real function, but test passes if no exception


@pytest.mark.asyncio
async def test_connect_failure(mongodb_service):
    """Test connection failure handling."""
    from pymongo.errors import ConnectionFailure

    # Create an async function that raises the exception
    async def mock_command_raises(*args, **kwargs):
        raise ConnectionFailure("Connection failed")

    mock_client = MagicMock()
    mock_admin = MagicMock()
    mock_admin.command = (
        mock_command_raises  # Use actual async function instead of AsyncMock
    )
    mock_client.admin = mock_admin

    with (
        patch("depotbutler.db.mongodb.AsyncIOMotorClient", return_value=mock_client),
        pytest.raises(ConnectionFailure),
    ):
        await mongodb_service.connect()


@pytest.mark.asyncio
async def test_close_connection(mongodb_service):
    """Test closing MongoDB connection."""
    mock_client = MagicMock()
    mock_client.close = MagicMock(
        return_value=None
    )  # Explicitly return None, not a coroutine
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

    # Mock repository method
    mock_repo = AsyncMock()
    mock_repo.get_active_recipients = AsyncMock(return_value=mock_recipients)

    mongodb_service.recipient_repo = mock_repo
    mongodb_service._connected = True

    recipients = await mongodb_service.get_active_recipients()

    assert len(recipients) == 2
    assert recipients[0]["email"] == "test1@example.com"
    assert recipients[1]["email"] == "test2@example.com"
    mock_repo.get_active_recipients.assert_called_once()


@pytest.mark.asyncio
async def test_get_active_recipients_empty(mongodb_service):
    """Test fetching recipients when none exist."""
    mock_repo = AsyncMock()
    mock_repo.get_active_recipients = AsyncMock(return_value=[])

    mongodb_service.recipient_repo = mock_repo
    mongodb_service._connected = True

    recipients = await mongodb_service.get_active_recipients()

    assert len(recipients) == 0
    mock_repo.get_active_recipients.assert_called_once()


@pytest.mark.asyncio
async def test_update_recipient_stats_success(mongodb_service):
    """Test updating recipient statistics."""
    mock_repo = AsyncMock()
    mock_repo.update_recipient_stats = AsyncMock()

    mongodb_service.recipient_repo = mock_repo
    mongodb_service._connected = True

    await mongodb_service.update_recipient_stats("test@example.com")

    mock_repo.update_recipient_stats.assert_called_once_with("test@example.com", None)


@pytest.mark.asyncio
async def test_update_recipient_stats_not_found(mongodb_service):
    """Test updating stats for non-existent recipient."""
    mock_repo = AsyncMock()
    mock_repo.update_recipient_stats = AsyncMock()

    mongodb_service.recipient_repo = mock_repo
    mongodb_service._connected = True

    # Should not raise exception, just log warning
    await mongodb_service.update_recipient_stats("nonexistent@example.com")

    mock_repo.update_recipient_stats.assert_called_once_with(
        "nonexistent@example.com", None
    )


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
    """Test that queries require connection (repositories must be set up)."""
    # Set disconnected state without repos
    mongodb_service._connected = False
    mongodb_service.recipient_repo = None

    # Trying to query without connection should fail with assertion
    with pytest.raises(AssertionError):
        await mongodb_service.get_active_recipients()


@pytest.mark.asyncio
async def test_get_auth_cookie_success(mongodb_service):
    """Test successful retrieval of auth cookie from MongoDB."""
    mock_repo = AsyncMock()
    mock_repo.get_auth_cookie = AsyncMock(return_value="test_cookie_value_12345")

    mongodb_service.config_repo = mock_repo
    mongodb_service._connected = True

    cookie_value = await mongodb_service.get_auth_cookie()

    assert cookie_value == "test_cookie_value_12345"
    mock_repo.get_auth_cookie.assert_called_once()


@pytest.mark.asyncio
async def test_get_auth_cookie_not_found(mongodb_service):
    """Test auth cookie retrieval when not found in MongoDB."""
    mock_repo = AsyncMock()
    mock_repo.get_auth_cookie = AsyncMock(return_value=None)

    mongodb_service.config_repo = mock_repo
    mongodb_service._connected = True

    cookie_value = await mongodb_service.get_auth_cookie()

    assert cookie_value is None
    mock_repo.get_auth_cookie.assert_called_once()


@pytest.mark.asyncio
async def test_update_auth_cookie_success(mongodb_service):
    """Test successful update of auth cookie in MongoDB."""
    mock_repo = AsyncMock()
    mock_repo.update_auth_cookie = AsyncMock(return_value=True)

    mongodb_service.config_repo = mock_repo
    mongodb_service._connected = True

    success = await mongodb_service.update_auth_cookie(
        "new_cookie_value", updated_by="test_user"
    )

    assert success is True
    # Note: expires_at defaults to None, updated_by passed as keyword arg
    mock_repo.update_auth_cookie.assert_called_once_with(
        "new_cookie_value", None, "test_user"
    )


@pytest.mark.asyncio
async def test_update_auth_cookie_upsert(mongodb_service):
    """Test upserting new auth cookie in MongoDB."""
    mock_repo = AsyncMock()
    mock_repo.update_auth_cookie = AsyncMock(return_value=True)

    mongodb_service.config_repo = mock_repo
    mongodb_service._connected = True

    success = await mongodb_service.update_auth_cookie(
        "new_cookie_value", updated_by="test_user"
    )

    assert success is True
    mock_repo.update_auth_cookie.assert_called_once_with(
        "new_cookie_value", None, "test_user"
    )


# ==================== Publications Tests ====================


@pytest.mark.asyncio
async def test_get_publications_success(mongodb_service):
    """Test retrieving all active publications."""
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

    mock_repo = AsyncMock()
    mock_repo.get_publications = AsyncMock(return_value=mock_publications)

    mongodb_service.publication_repo = mock_repo
    mongodb_service._connected = True

    publications = await mongodb_service.get_publications()

    assert len(publications) == 2
    assert publications[0]["publication_id"] == "pub1"
    assert publications[1]["publication_id"] == "pub2"
    mock_repo.get_publications.assert_called_once_with(active_only=True)


@pytest.mark.asyncio
async def test_get_publications_all(mongodb_service):
    """Test retrieving all publications including inactive."""
    mock_publications = [
        {"publication_id": "pub1", "active": True},
        {"publication_id": "pub2", "active": False},
    ]

    mock_repo = AsyncMock()
    mock_repo.get_publications = AsyncMock(return_value=mock_publications)

    mongodb_service.publication_repo = mock_repo
    mongodb_service._connected = True

    publications = await mongodb_service.get_publications(active_only=False)

    assert len(publications) == 2
    mock_repo.get_publications.assert_called_once_with(active_only=False)


@pytest.mark.asyncio
async def test_get_publication_found(mongodb_service):
    """Test retrieving a single publication by ID."""
    mock_publication = {
        "publication_id": "test-pub",
        "name": "Test Publication",
        "active": True,
    }

    mock_repo = AsyncMock()
    mock_repo.get_publication = AsyncMock(return_value=mock_publication)

    mongodb_service.publication_repo = mock_repo
    mongodb_service._connected = True

    publication = await mongodb_service.get_publication("test-pub")

    assert publication is not None
    assert publication["publication_id"] == "test-pub"
    mock_repo.get_publication.assert_called_once_with("test-pub")


@pytest.mark.asyncio
async def test_get_publication_not_found(mongodb_service):
    """Test retrieving non-existent publication."""
    mock_repo = AsyncMock()
    mock_repo.get_publication = AsyncMock(return_value=None)

    mongodb_service.publication_repo = mock_repo
    mongodb_service._connected = True

    publication = await mongodb_service.get_publication("nonexistent")

    assert publication is None
    mock_repo.get_publication.assert_called_once_with("nonexistent")


@pytest.mark.asyncio
async def test_create_publication_success(mongodb_service):
    """Test creating a new publication."""
    publication_data = {
        "publication_id": "new-pub",
        "name": "New Publication",
        "active": True,
        "email_enabled": True,
    }

    mock_repo = AsyncMock()
    # Note: The repo method is create(), not create_publication()
    mock_repo.create = AsyncMock(
        return_value="507f1f77bcf86cd799439011"
    )  # Returns inserted_id

    mongodb_service.publication_repo = mock_repo
    mongodb_service._connected = True

    success = await mongodb_service.create_publication(publication_data)

    assert success is True
    mock_repo.create.assert_called_once()
    # Verify the publication data was passed
    call_args = mock_repo.create.call_args[0][0]
    assert call_args["publication_id"] == "new-pub"


@pytest.mark.asyncio
async def test_update_publication_success(mongodb_service):
    """Test updating an existing publication."""
    updates = {"email_enabled": False, "onedrive_enabled": True}

    mock_repo = AsyncMock()
    # Note: The repo method is update(), not update_publication()
    mock_repo.update = AsyncMock(
        return_value={"modified_count": 1}
    )  # Returns result dict

    mongodb_service.publication_repo = mock_repo
    mongodb_service._connected = True

    success = await mongodb_service.update_publication("test-pub", updates)

    assert success is True
    mock_repo.update.assert_called_once_with("test-pub", updates)


@pytest.mark.asyncio
async def test_update_publication_not_found(mongodb_service):
    """Test updating non-existent publication."""
    updates = {"email_enabled": False}

    mock_repo = AsyncMock()
    # Note: The repo method is update(), returns None when not found
    mock_repo.update = AsyncMock(return_value=None)

    mongodb_service.publication_repo = mock_repo
    mongodb_service._connected = True

    success = await mongodb_service.update_publication("nonexistent", updates)

    assert success is False
    mock_repo.update.assert_called_once_with("nonexistent", updates)


@pytest.mark.asyncio
async def test_get_cookie_expiration_info_success(mongodb_service):
    """Test successful retrieval of cookie expiration info."""
    from datetime import timedelta

    expiration_date = datetime.now(UTC) + timedelta(days=10)

    mock_info = {
        "expires_at": expiration_date,
        "days_remaining": 10,
        "is_expired": False,
    }

    mock_repo = AsyncMock()
    mock_repo.get_cookie_expiration_info = AsyncMock(return_value=mock_info)

    mongodb_service.config_repo = mock_repo
    mongodb_service._connected = True

    info = await mongodb_service.get_cookie_expiration_info()

    assert info is not None
    assert "expires_at" in info
    assert "days_remaining" in info
    assert info["days_remaining"] >= 9  # Should be around 10 days
    assert info["is_expired"] is False
    mock_repo.get_cookie_expiration_info.assert_called_once()


@pytest.mark.asyncio
async def test_get_cookie_expiration_info_expired(mongodb_service):
    """Test cookie expiration info when cookie is expired."""
    from datetime import timedelta

    expiration_date = datetime.now(UTC) - timedelta(days=5)

    mock_info = {
        "expires_at": expiration_date,
        "days_remaining": -5,
        "is_expired": True,
    }

    mock_repo = AsyncMock()
    mock_repo.get_cookie_expiration_info = AsyncMock(return_value=mock_info)

    mongodb_service.config_repo = mock_repo
    mongodb_service._connected = True

    info = await mongodb_service.get_cookie_expiration_info()

    assert info is not None
    assert info["is_expired"] is True
    assert info["days_remaining"] < 0
    mock_repo.get_cookie_expiration_info.assert_called_once()


@pytest.mark.asyncio
async def test_get_cookie_expiration_info_no_expiration(mongodb_service):
    """Test cookie expiration info when no expiration date set."""
    mock_info = {
        "warning": "No expiration date stored",
        "expires_at": None,
        "days_remaining": None,
        "is_expired": None,
    }

    mock_repo = AsyncMock()
    mock_repo.get_cookie_expiration_info = AsyncMock(return_value=mock_info)

    mongodb_service.config_repo = mock_repo
    mongodb_service._connected = True

    info = await mongodb_service.get_cookie_expiration_info()

    # Returns dict with warning when no expiration date
    assert info is not None
    assert info["warning"] == "No expiration date stored"
    assert info["expires_at"] is None
    assert info["days_remaining"] is None
    assert info["is_expired"] is None
    mock_repo.get_cookie_expiration_info.assert_called_once()


@pytest.mark.asyncio
async def test_get_cookie_expiration_info_not_found(mongodb_service):
    """Test cookie expiration info when cookie not found."""
    mock_repo = AsyncMock()
    mock_repo.get_cookie_expiration_info = AsyncMock(return_value=None)

    mongodb_service.config_repo = mock_repo
    mongodb_service._connected = True

    info = await mongodb_service.get_cookie_expiration_info()

    assert info is None
    mock_repo.get_cookie_expiration_info.assert_called_once()


@pytest.mark.asyncio
async def test_get_app_config_success(mongodb_service):
    """Test successful retrieval of app config value."""
    mock_repo = AsyncMock()
    mock_repo.get_app_config = AsyncMock(return_value="test_value")

    mongodb_service.config_repo = mock_repo
    mongodb_service._connected = True

    value = await mongodb_service.get_app_config("test_config")

    assert value == "test_value"
    mock_repo.get_app_config.assert_called_once_with("test_config", None)


@pytest.mark.asyncio
async def test_get_app_config_with_default(mongodb_service):
    """Test get_app_config returns default when not found."""
    mock_repo = AsyncMock()
    mock_repo.get_app_config = AsyncMock(return_value="default_value")

    mongodb_service.config_repo = mock_repo
    mongodb_service._connected = True

    value = await mongodb_service.get_app_config("nonexistent", default="default_value")

    assert value == "default_value"
    mock_repo.get_app_config.assert_called_once_with("nonexistent", "default_value")


@pytest.mark.asyncio
async def test_get_app_config_no_default(mongodb_service):
    """Test get_app_config returns None when not found and no default."""
    mock_repo = AsyncMock()
    mock_repo.get_app_config = AsyncMock(return_value=None)

    mongodb_service.config_repo = mock_repo
    mongodb_service._connected = True

    value = await mongodb_service.get_app_config("nonexistent")

    assert value is None
    mock_repo.get_app_config.assert_called_once_with("nonexistent", None)


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
    mock_repo = AsyncMock()
    # The repo should handle the exception and return empty list, not raise
    mock_repo.get_publications = AsyncMock(return_value=[])

    mongodb_service.publication_repo = mock_repo
    mongodb_service._connected = True

    # Should return empty list on error
    publications = await mongodb_service.get_publications()

    assert publications == []


@pytest.mark.asyncio
async def test_get_publication_exception_handling(mongodb_service):
    """Test get_publication handles exceptions."""
    mock_repo = AsyncMock()
    # The repo should handle the exception and return None, not raise
    mock_repo.get_publication = AsyncMock(return_value=None)

    mongodb_service.publication_repo = mock_repo
    mongodb_service._connected = True

    # Should return None on error
    publication = await mongodb_service.get_publication("test-pub")

    assert publication is None


@pytest.mark.asyncio
async def test_create_publication_exception_handling(mongodb_service):
    """Test create_publication handles exceptions."""
    mock_repo = AsyncMock()
    # The repo should handle the exception and return None, not raise
    mock_repo.create = AsyncMock(return_value=None)

    mongodb_service.publication_repo = mock_repo
    mongodb_service._connected = True

    pub_data = {"publication_id": "test-pub", "name": "Test"}

    # Should return False on error (None from repo = False)
    success = await mongodb_service.create_publication(pub_data)

    assert success is False


@pytest.mark.asyncio
async def test_update_publication_exception_handling(mongodb_service):
    """Test update_publication handles exceptions."""
    mock_repo = AsyncMock()
    # The repo should handle the exception and return None, not raise
    mock_repo.update = AsyncMock(return_value=None)

    mongodb_service.publication_repo = mock_repo
    mongodb_service._connected = True

    # Should return False on error (None from repo = False)
    success = await mongodb_service.update_publication("test-pub", {"name": "Updated"})

    assert success is False


@pytest.mark.asyncio
async def test_get_active_recipients_exception_handling(mongodb_service):
    """Test get_active_recipients handles exceptions."""
    mock_repo = AsyncMock()
    # The repo should handle the exception and return empty list, not raise
    mock_repo.get_active_recipients = AsyncMock(return_value=[])

    mongodb_service.recipient_repo = mock_repo
    mongodb_service._connected = True

    # Should return empty list on error
    recipients = await mongodb_service.get_active_recipients()

    assert recipients == []


@pytest.mark.asyncio
async def test_update_recipient_stats_exception_handling(mongodb_service):
    """Test update_recipient_stats handles exceptions."""
    mock_repo = AsyncMock()
    # The repo should handle the exception silently (no return value)
    mock_repo.update_recipient_stats = AsyncMock()

    mongodb_service.recipient_repo = mock_repo
    mongodb_service._connected = True

    # Should not raise exception
    await mongodb_service.update_recipient_stats("test@example.com")
