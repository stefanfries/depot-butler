"""Unit tests for ConfigRepository."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from depotbutler.db.repositories.config import ConfigRepository


@pytest.fixture
def config_repo():
    """Mock ConfigRepository with AsyncMock collection."""
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_collection = AsyncMock()

    # Mock the config collection
    mock_db.config = mock_collection
    mock_client.__getitem__ = MagicMock(return_value=mock_db)

    repo = ConfigRepository(client=mock_client, db_name="test_db")
    return repo


class TestAuthCookie:
    """Tests for auth cookie operations."""

    @pytest.mark.asyncio
    async def test_get_auth_cookie_success(self, config_repo):
        """Successfully retrieve auth cookie."""
        config_repo.collection.find_one = AsyncMock(
            return_value={
                "_id": "auth_cookie",
                "cookie_value": "test_cookie_value_123",
                "updated_at": datetime.now(UTC),
            }
        )

        result = await config_repo.get_auth_cookie()

        assert result == "test_cookie_value_123"
        config_repo.collection.find_one.assert_called_once_with({"_id": "auth_cookie"})

    @pytest.mark.asyncio
    async def test_get_auth_cookie_not_found(self, config_repo):
        """Auth cookie not found - returns None."""
        config_repo.collection.find_one = AsyncMock(return_value=None)

        result = await config_repo.get_auth_cookie()

        assert result is None

    @pytest.mark.asyncio
    async def test_get_auth_cookie_empty_value(self, config_repo):
        """Auth cookie document exists but has empty value."""
        config_repo.collection.find_one = AsyncMock(
            return_value={
                "_id": "auth_cookie",
                "cookie_value": "",
            }
        )

        result = await config_repo.get_auth_cookie()

        assert result is None

    @pytest.mark.asyncio
    async def test_get_auth_cookie_handles_error(self, config_repo):
        """Database error - returns None."""
        config_repo.collection.find_one = AsyncMock(side_effect=Exception("DB error"))

        result = await config_repo.get_auth_cookie()

        assert result is None

    @pytest.mark.asyncio
    async def test_update_auth_cookie_success(self, config_repo):
        """Successfully update auth cookie."""
        mock_result = MagicMock()
        mock_result.modified_count = 1
        mock_result.upserted_id = None
        config_repo.collection.update_one = AsyncMock(return_value=mock_result)

        expires_at = datetime.now(UTC) + timedelta(days=7)
        result = await config_repo.update_auth_cookie(
            cookie_value="new_cookie_123", expires_at=expires_at, updated_by="test_user"
        )

        assert result is True
        config_repo.collection.update_one.assert_called_once()

        # Verify update structure
        call_args = config_repo.collection.update_one.call_args
        assert call_args[0][0] == {"_id": "auth_cookie"}
        assert "$set" in call_args[0][1]
        assert call_args[1]["upsert"] is True

        update_doc = call_args[0][1]["$set"]
        assert update_doc["cookie_value"] == "new_cookie_123"
        assert update_doc["expires_at"] == expires_at
        assert update_doc["updated_by"] == "test_user"
        assert "updated_at" in update_doc

    @pytest.mark.asyncio
    async def test_update_auth_cookie_upsert(self, config_repo):
        """Update creates new document when not exists (upsert)."""
        mock_result = MagicMock()
        mock_result.modified_count = 0
        mock_result.upserted_id = "new_id"
        config_repo.collection.update_one = AsyncMock(return_value=mock_result)

        result = await config_repo.update_auth_cookie("cookie_value")

        assert result is True

    @pytest.mark.asyncio
    async def test_update_auth_cookie_no_effect(self, config_repo):
        """Update has no effect - returns False."""
        mock_result = MagicMock()
        mock_result.modified_count = 0
        mock_result.upserted_id = None
        config_repo.collection.update_one = AsyncMock(return_value=mock_result)

        result = await config_repo.update_auth_cookie("cookie_value")

        assert result is False

    @pytest.mark.asyncio
    async def test_update_auth_cookie_handles_error(self, config_repo):
        """Database error - returns False."""
        config_repo.collection.update_one = AsyncMock(side_effect=Exception("DB error"))

        result = await config_repo.update_auth_cookie("cookie_value")

        assert result is False


class TestCookieExpiration:
    """Tests for cookie expiration info."""

    @pytest.mark.asyncio
    async def test_get_cookie_expiration_valid(self, config_repo):
        """Get expiration info for valid cookie."""
        expires_at = datetime.now(UTC) + timedelta(days=5)
        config_repo.collection.find_one = AsyncMock(
            return_value={
                "_id": "auth_cookie",
                "expires_at": expires_at,
                "updated_at": datetime.now(UTC),
                "updated_by": "test_user",
            }
        )

        result = await config_repo.get_cookie_expiration_info()

        assert result is not None
        assert result["expires_at"] == expires_at
        assert result["days_remaining"] >= 4  # Allow for timing variance
        assert result["days_remaining"] <= 5
        assert result["is_expired"] is False
        assert "updated_at" in result
        assert "updated_by" in result

    @pytest.mark.asyncio
    async def test_get_cookie_expiration_expired(self, config_repo):
        """Get expiration info for expired cookie."""
        expires_at = datetime.now(UTC) - timedelta(days=2)
        config_repo.collection.find_one = AsyncMock(
            return_value={
                "_id": "auth_cookie",
                "expires_at": expires_at,
            }
        )

        result = await config_repo.get_cookie_expiration_info()

        assert result is not None
        assert result["days_remaining"] < 0
        assert result["is_expired"] is True

    @pytest.mark.asyncio
    async def test_get_cookie_expiration_no_date(self, config_repo):
        """Cookie exists but has no expiration date."""
        config_repo.collection.find_one = AsyncMock(
            return_value={
                "_id": "auth_cookie",
                "cookie_value": "test",
            }
        )

        result = await config_repo.get_cookie_expiration_info()

        assert result is not None
        assert result["expires_at"] is None
        assert result["days_remaining"] is None
        assert result["is_expired"] is None
        assert "warning" in result

    @pytest.mark.asyncio
    async def test_get_cookie_expiration_not_found(self, config_repo):
        """Cookie document not found - returns None."""
        config_repo.collection.find_one = AsyncMock(return_value=None)

        result = await config_repo.get_cookie_expiration_info()

        assert result is None

    @pytest.mark.asyncio
    async def test_get_cookie_expiration_handles_error(self, config_repo):
        """Database error - returns None."""
        config_repo.collection.find_one = AsyncMock(side_effect=Exception("DB error"))

        result = await config_repo.get_cookie_expiration_info()

        assert result is None


class TestAppConfig:
    """Tests for application configuration."""

    @pytest.mark.asyncio
    async def test_get_app_config_existing_key(self, config_repo):
        """Get existing configuration value."""
        config_repo.collection.find_one = AsyncMock(
            return_value={
                "_id": "app_config",
                "log_level": "DEBUG",
                "cookie_warning_days": 5,
            }
        )

        result = await config_repo.get_app_config("log_level")

        assert result == "DEBUG"

    @pytest.mark.asyncio
    async def test_get_app_config_with_default(self, config_repo):
        """Get config with default value."""
        config_repo.collection.find_one = AsyncMock(
            return_value={
                "_id": "app_config",
                "other_key": "value",
            }
        )

        result = await config_repo.get_app_config("log_level", default="INFO")

        assert result == "INFO"

    @pytest.mark.asyncio
    async def test_get_app_config_overrides_default(self, config_repo):
        """Config value overrides default."""
        config_repo.collection.find_one = AsyncMock(
            return_value={
                "_id": "app_config",
                "log_level": "DEBUG",
            }
        )

        result = await config_repo.get_app_config("log_level", default="INFO")

        assert result == "DEBUG"

    @pytest.mark.asyncio
    async def test_get_app_config_not_found_no_default(self, config_repo):
        """Config not found and no default - returns None."""
        config_repo.collection.find_one = AsyncMock(return_value=None)

        result = await config_repo.get_app_config("missing_key")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_app_config_handles_error_with_default(self, config_repo):
        """Database error - returns default value."""
        config_repo.collection.find_one = AsyncMock(side_effect=Exception("DB error"))

        result = await config_repo.get_app_config("log_level", default="INFO")

        assert result == "INFO"

    @pytest.mark.asyncio
    async def test_update_app_config_success(self, config_repo):
        """Successfully update app config."""
        mock_result = MagicMock()
        mock_result.modified_count = 1
        mock_result.upserted_id = None
        config_repo.collection.update_one = AsyncMock(return_value=mock_result)

        updates = {"log_level": "DEBUG", "cookie_warning_days": 3}
        result = await config_repo.update_app_config(updates)

        assert result is True
        config_repo.collection.update_one.assert_called_once()

        # Verify update structure
        call_args = config_repo.collection.update_one.call_args
        assert call_args[0][0] == {"_id": "app_config"}
        assert call_args[0][1] == {"$set": updates}
        assert call_args[1]["upsert"] is True

    @pytest.mark.asyncio
    async def test_update_app_config_upsert(self, config_repo):
        """Update creates new config document (upsert)."""
        mock_result = MagicMock()
        mock_result.modified_count = 0
        mock_result.upserted_id = "new_id"
        config_repo.collection.update_one = AsyncMock(return_value=mock_result)

        result = await config_repo.update_app_config({"key": "value"})

        assert result is True

    @pytest.mark.asyncio
    async def test_update_app_config_no_effect(self, config_repo):
        """Update has no effect - returns False."""
        mock_result = MagicMock()
        mock_result.modified_count = 0
        mock_result.upserted_id = None
        config_repo.collection.update_one = AsyncMock(return_value=mock_result)

        result = await config_repo.update_app_config({"key": "value"})

        assert result is False

    @pytest.mark.asyncio
    async def test_update_app_config_handles_error(self, config_repo):
        """Database error - returns False."""
        config_repo.collection.update_one = AsyncMock(side_effect=Exception("DB error"))

        result = await config_repo.update_app_config({"key": "value"})

        assert result is False
