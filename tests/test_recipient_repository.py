"""Unit tests for RecipientRepository."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from depotbutler.db.repositories.recipient import RecipientRepository


@pytest.fixture
def recipient_repo():
    """Mock RecipientRepository with AsyncMock collection."""
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_collection = AsyncMock()

    # Mock the recipients collection
    mock_db.recipients = mock_collection
    mock_client.__getitem__ = MagicMock(return_value=mock_db)

    repo = RecipientRepository(client=mock_client, db_name="test_db")
    return repo


@pytest.fixture
def sample_recipient():
    """Sample recipient document."""
    return {
        "email": "test@example.com",
        "first_name": "Test",
        "last_name": "User",
        "active": True,
        "publication_preferences": [
            {
                "publication_id": "test-pub",
                "enabled": True,
                "email_enabled": True,
                "upload_enabled": True,
                "custom_onedrive_folder": "Custom/Folder",
                "organize_by_year": False,
                "send_count": 5,
                "last_sent_at": datetime(2025, 12, 20, 12, 0, 0),
            }
        ],
    }


@pytest.fixture
def sample_publication():
    """Sample publication document."""
    return {
        "publication_id": "test-pub",
        "title": "Test Publication",
        "default_onedrive_folder": "Default/Folder",
        "organize_by_year": True,
    }


class TestGetRecipientsForPublication:
    """Test get_recipients_for_publication method."""

    @pytest.mark.asyncio
    async def test_get_recipients_email_method(self, recipient_repo, sample_recipient):
        """Test filtering recipients for email delivery."""
        mock_cursor = AsyncMock()
        mock_cursor.to_list = AsyncMock(return_value=[sample_recipient])
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        recipient_repo.collection.find = MagicMock(return_value=mock_cursor)

        recipients = await recipient_repo.get_recipients_for_publication(
            "test-pub", "email"
        )

        assert len(recipients) == 1
        assert recipients[0]["email"] == "test@example.com"
        recipient_repo.collection.find.assert_called_once()

        # Verify query structure
        call_args = recipient_repo.collection.find.call_args[0]
        query = call_args[0]
        assert query["active"] is True
        assert "publication_preferences" in query
        assert (
            query["publication_preferences"]["$elemMatch"]["publication_id"]
            == "test-pub"
        )
        assert query["publication_preferences"]["$elemMatch"]["email_enabled"] is True

    @pytest.mark.asyncio
    async def test_get_recipients_upload_method(self, recipient_repo, sample_recipient):
        """Test filtering recipients for upload delivery."""
        mock_cursor = AsyncMock()
        mock_cursor.to_list = AsyncMock(return_value=[sample_recipient])
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        recipient_repo.collection.find = MagicMock(return_value=mock_cursor)

        recipients = await recipient_repo.get_recipients_for_publication(
            "test-pub", "upload"
        )

        assert len(recipients) == 1
        # Verify upload_enabled was checked
        call_args = recipient_repo.collection.find.call_args[0]
        query = call_args[0]
        assert query["publication_preferences"]["$elemMatch"]["upload_enabled"] is True

    @pytest.mark.asyncio
    async def test_get_recipients_invalid_method(self, recipient_repo):
        """Test invalid delivery method returns empty list."""
        recipients = await recipient_repo.get_recipients_for_publication(
            "test-pub", "invalid"
        )

        assert recipients == []
        recipient_repo.collection.find.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_recipients_no_matching_recipients(self, recipient_repo):
        """Test when no recipients match criteria."""
        mock_cursor = AsyncMock()
        mock_cursor.to_list = AsyncMock(return_value=[])
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        recipient_repo.collection.find = MagicMock(return_value=mock_cursor)

        recipients = await recipient_repo.get_recipients_for_publication(
            "nonexistent-pub", "email"
        )

        assert recipients == []

    @pytest.mark.asyncio
    async def test_get_recipients_database_error(self, recipient_repo):
        """Test handling of database errors."""
        mock_cursor = AsyncMock()
        mock_cursor.to_list = AsyncMock(side_effect=Exception("Database error"))
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        recipient_repo.collection.find = MagicMock(return_value=mock_cursor)

        recipients = await recipient_repo.get_recipients_for_publication(
            "test-pub", "email"
        )

        assert recipients == []


class TestGetRecipientPreference:
    """Test get_recipient_preference method."""

    def test_preference_uses_recipient_override(
        self, recipient_repo, sample_recipient, sample_publication
    ):
        """Test that recipient custom preference takes priority."""
        result = recipient_repo.get_recipient_preference(
            sample_recipient,
            sample_publication,
            "custom_onedrive_folder",
            "default_onedrive_folder",
            "",
        )

        assert result == "Custom/Folder"

    def test_preference_falls_back_to_publication(
        self, recipient_repo, sample_publication
    ):
        """Test fallback to publication default when no recipient preference."""
        recipient_no_pref = {
            "email": "test@example.com",
            "publication_preferences": [],
        }

        result = recipient_repo.get_recipient_preference(
            recipient_no_pref,
            sample_publication,
            "custom_onedrive_folder",
            "default_onedrive_folder",
            "",
        )

        assert result == "Default/Folder"

    def test_preference_uses_default_when_not_found(
        self, recipient_repo, sample_recipient
    ):
        """Test default value when not in recipient or publication."""
        publication_no_folder = {
            "publication_id": "test-pub",
            # No default_onedrive_folder field
        }

        result = recipient_repo.get_recipient_preference(
            sample_recipient,
            publication_no_folder,
            "nonexistent_key",
            "nonexistent_key",
            "default_value",
        )

        assert result == "default_value"

    def test_preference_with_different_pub_key(
        self, recipient_repo, sample_recipient, sample_publication
    ):
        """Test using different keys for recipient and publication."""
        result = recipient_repo.get_recipient_preference(
            sample_recipient,
            sample_publication,
            "organize_by_year",  # recipient key
            "organize_by_year",  # publication key
            True,
        )

        # Recipient has organize_by_year=False, should use that
        assert result is False


class TestGetOnedriveFolderForRecipient:
    """Test get_onedrive_folder_for_recipient method."""

    def test_custom_folder_takes_priority(
        self, recipient_repo, sample_recipient, sample_publication
    ):
        """Test that custom folder overrides publication default."""
        folder = recipient_repo.get_onedrive_folder_for_recipient(
            sample_recipient, sample_publication
        )

        assert folder == "Custom/Folder"

    def test_fallback_to_publication_default(self, recipient_repo, sample_publication):
        """Test fallback when recipient has no custom folder."""
        recipient_no_custom = {
            "email": "test@example.com",
            "publication_preferences": [
                {
                    "publication_id": "test-pub",
                    "enabled": True,
                    # No custom_onedrive_folder
                }
            ],
        }

        folder = recipient_repo.get_onedrive_folder_for_recipient(
            recipient_no_custom, sample_publication
        )

        assert folder == "Default/Folder"

    def test_empty_folder_when_not_set(self, recipient_repo):
        """Test returns empty string when no folder configured."""
        recipient_no_prefs = {
            "email": "test@example.com",
            "publication_preferences": [],
        }
        publication_no_folder = {"publication_id": "test-pub"}

        folder = recipient_repo.get_onedrive_folder_for_recipient(
            recipient_no_prefs, publication_no_folder
        )

        assert folder == ""


class TestGetOrganizeByYearForRecipient:
    """Test get_organize_by_year_for_recipient method."""

    def test_recipient_override_false(
        self, recipient_repo, sample_recipient, sample_publication
    ):
        """Test recipient can override to False."""
        # sample_recipient has organize_by_year=False
        # sample_publication has organize_by_year=True
        result = recipient_repo.get_organize_by_year_for_recipient(
            sample_recipient, sample_publication
        )

        assert result is False

    def test_recipient_override_true(self, recipient_repo, sample_publication):
        """Test recipient can override to True."""
        recipient_override_true = {
            "email": "test@example.com",
            "publication_preferences": [
                {
                    "publication_id": "test-pub",
                    "enabled": True,
                    "organize_by_year": True,
                }
            ],
        }
        publication_false = {
            "publication_id": "test-pub",
            "organize_by_year": False,
        }

        result = recipient_repo.get_organize_by_year_for_recipient(
            recipient_override_true, publication_false
        )

        assert result is True

    def test_fallback_to_publication_setting(self, recipient_repo, sample_publication):
        """Test uses publication setting when no recipient preference."""
        recipient_no_pref = {
            "email": "test@example.com",
            "publication_preferences": [
                {
                    "publication_id": "test-pub",
                    "enabled": True,
                    # No organize_by_year
                }
            ],
        }

        result = recipient_repo.get_organize_by_year_for_recipient(
            recipient_no_pref, sample_publication
        )

        assert result is True

    def test_default_to_true_when_not_set(self, recipient_repo):
        """Test defaults to True when not set anywhere."""
        recipient_no_prefs = {
            "email": "test@example.com",
            "publication_preferences": [],
        }
        publication_no_setting = {"publication_id": "test-pub"}

        result = recipient_repo.get_organize_by_year_for_recipient(
            recipient_no_prefs, publication_no_setting
        )

        assert result is True


class TestUpdateRecipientStats:
    """Test update_recipient_stats method."""

    @pytest.mark.asyncio
    async def test_update_stats_with_publication_id(self, recipient_repo):
        """Test updating per-publication stats."""
        mock_result = MagicMock()
        mock_result.modified_count = 1
        recipient_repo.collection.update_one = AsyncMock(return_value=mock_result)

        await recipient_repo.update_recipient_stats("test@example.com", "test-pub")

        recipient_repo.collection.update_one.assert_called_once()
        call_args = recipient_repo.collection.update_one.call_args[0]

        # Verify query filters correctly
        query = call_args[0]
        assert query["email"] == "test@example.com"
        assert query["publication_preferences.publication_id"] == "test-pub"

        # Verify update operations
        update = call_args[1]
        assert "$set" in update
        assert "$inc" in update
        assert update["$inc"]["publication_preferences.$.send_count"] == 1

    @pytest.mark.asyncio
    async def test_update_stats_legacy_mode(self, recipient_repo):
        """Test updating global stats (no publication_id)."""
        mock_result = MagicMock()
        mock_result.modified_count = 1
        recipient_repo.collection.update_one = AsyncMock(return_value=mock_result)

        await recipient_repo.update_recipient_stats("test@example.com")

        call_args = recipient_repo.collection.update_one.call_args[0]
        query = call_args[0]
        assert query == {"email": "test@example.com"}

        update = call_args[1]
        assert "$set" in update
        assert "$inc" in update
        assert update["$inc"]["send_count"] == 1

    @pytest.mark.asyncio
    async def test_update_stats_recipient_not_found(self, recipient_repo):
        """Test when recipient doesn't exist."""
        mock_result = MagicMock()
        mock_result.modified_count = 0  # No documents modified
        recipient_repo.collection.update_one = AsyncMock(return_value=mock_result)

        # Should not raise exception
        await recipient_repo.update_recipient_stats(
            "nonexistent@example.com", "test-pub"
        )

        recipient_repo.collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_stats_database_error(self, recipient_repo):
        """Test handling of database errors."""
        recipient_repo.collection.update_one = AsyncMock(
            side_effect=Exception("Database error")
        )

        # Should not raise exception (error logged)
        await recipient_repo.update_recipient_stats("test@example.com", "test-pub")
