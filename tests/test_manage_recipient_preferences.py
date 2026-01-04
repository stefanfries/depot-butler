"""
Tests for manage_recipient_preferences.py script.

Tests the admin tool for managing recipient publication preferences.
"""

# Import functions from the script
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from manage_recipient_preferences import (
    add_preference,
    bulk_add_preference,
    bulk_remove_preference,
    list_preferences,
    remove_preference,
    show_statistics,
)


@pytest.fixture
def mock_mongodb_service():
    """Create a mock MongoDB service."""
    service = MagicMock()
    # Mock db as an object with collection attributes, not a dict
    service.db = MagicMock()
    service.db.recipients = AsyncMock()
    service.db.publications = AsyncMock()
    service.get_publications = AsyncMock()
    service.close = AsyncMock()
    return service


@pytest.fixture
def sample_recipient():
    """Sample recipient document."""
    return {
        "email": "user@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "active": True,
        "send_count": 5,
        "last_sent_at": "2026-01-01T12:00:00",
        "publication_preferences": [
            {
                "publication_id": "megatrend-folger",
                "enabled": True,
                "email_enabled": True,
                "upload_enabled": False,
                "custom_onedrive_folder": None,
                "organize_by_year": None,
                "send_count": 5,
                "last_sent_at": "2026-01-01T12:00:00",
            }
        ],
    }


@pytest.fixture
def sample_publication():
    """Sample publication document."""
    return {
        "publication_id": "aktionaer-epaper",
        "name": "DER AKTIONÄR E-Paper",
        "active": True,
    }


@pytest.mark.asyncio
class TestAddPreference:
    """Tests for add_preference function."""

    async def test_add_preference_success(
        self, mock_mongodb_service, sample_recipient, sample_publication
    ):
        """Test successfully adding a preference."""
        with patch(
            "manage_recipient_preferences.get_mongodb_service",
            return_value=mock_mongodb_service,
        ):
            # Setup mocks
            mock_mongodb_service.db.recipients.find_one = AsyncMock(
                return_value=sample_recipient
            )
            mock_mongodb_service.db.publications.find_one = AsyncMock(
                return_value=sample_publication
            )
            mock_mongodb_service.db.recipients.update_one = AsyncMock(
                return_value=MagicMock(modified_count=1)
            )

            # Execute
            result = await add_preference("user@example.com", "aktionaer-epaper")

            # Verify
            assert result is True
            mock_mongodb_service.db.recipients.update_one.assert_called_once()
            mock_mongodb_service.close.assert_called_once()

    async def test_add_preference_recipient_not_found(
        self, mock_mongodb_service, sample_publication
    ):
        """Test adding preference when recipient doesn't exist."""
        with patch(
            "manage_recipient_preferences.get_mongodb_service",
            return_value=mock_mongodb_service,
        ):
            # Setup mocks
            mock_mongodb_service.db.recipients.find_one = AsyncMock(return_value=None)

            # Execute
            result = await add_preference("nonexistent@example.com", "aktionaer-epaper")

            # Verify
            assert result is False
            mock_mongodb_service.close.assert_called_once()

    async def test_add_preference_publication_not_found(
        self, mock_mongodb_service, sample_recipient
    ):
        """Test adding preference when publication doesn't exist."""
        with patch(
            "manage_recipient_preferences.get_mongodb_service",
            return_value=mock_mongodb_service,
        ):
            # Setup mocks
            mock_mongodb_service.db.recipients.find_one = AsyncMock(
                return_value=sample_recipient
            )
            mock_mongodb_service.db.publications.find_one = AsyncMock(return_value=None)

            # Execute
            result = await add_preference("user@example.com", "nonexistent-pub")

            # Verify
            assert result is False
            mock_mongodb_service.close.assert_called_once()

    async def test_add_preference_already_exists(
        self, mock_mongodb_service, sample_recipient
    ):
        """Test adding preference that already exists."""
        with patch(
            "manage_recipient_preferences.get_mongodb_service",
            return_value=mock_mongodb_service,
        ):
            # Setup mocks
            mock_mongodb_service.db.recipients.find_one = AsyncMock(
                return_value=sample_recipient
            )
            sample_pub = {
                "publication_id": "megatrend-folger",
                "name": "Megatrend Folger",
            }
            mock_mongodb_service.db.publications.find_one = AsyncMock(
                return_value=sample_pub
            )

            # Execute (trying to add megatrend-folger which already exists)
            result = await add_preference("user@example.com", "megatrend-folger")

            # Verify
            assert result is False
            mock_mongodb_service.close.assert_called_once()

    async def test_add_preference_with_custom_settings(
        self, mock_mongodb_service, sample_recipient, sample_publication
    ):
        """Test adding preference with custom email/upload settings."""
        with patch(
            "manage_recipient_preferences.get_mongodb_service",
            return_value=mock_mongodb_service,
        ):
            # Setup mocks
            mock_mongodb_service.db.recipients.find_one = AsyncMock(
                return_value=sample_recipient
            )
            mock_mongodb_service.db.publications.find_one = AsyncMock(
                return_value=sample_publication
            )
            mock_mongodb_service.db.recipients.update_one = AsyncMock(
                return_value=MagicMock(modified_count=1)
            )

            # Execute with custom settings
            result = await add_preference(
                "user@example.com",
                "aktionaer-epaper",
                email_enabled=False,
                upload_enabled=True,
            )

            # Verify
            assert result is True


@pytest.mark.asyncio
class TestRemovePreference:
    """Tests for remove_preference function."""

    async def test_remove_preference_success(
        self, mock_mongodb_service, sample_recipient
    ):
        """Test successfully removing a preference."""
        with patch(
            "manage_recipient_preferences.get_mongodb_service",
            return_value=mock_mongodb_service,
        ):
            # Setup mocks
            mock_mongodb_service.db.recipients.find_one = AsyncMock(
                return_value=sample_recipient
            )
            mock_mongodb_service.db.recipients.update_one = AsyncMock(
                return_value=MagicMock(modified_count=1)
            )

            # Execute
            result = await remove_preference("user@example.com", "megatrend-folger")

            # Verify
            assert result is True
            mock_mongodb_service.db.recipients.update_one.assert_called_once()
            mock_mongodb_service.close.assert_called_once()

    async def test_remove_preference_recipient_not_found(self, mock_mongodb_service):
        """Test removing preference when recipient doesn't exist."""
        with patch(
            "manage_recipient_preferences.get_mongodb_service",
            return_value=mock_mongodb_service,
        ):
            # Setup mocks
            mock_mongodb_service.db.recipients.find_one = AsyncMock(return_value=None)

            # Execute
            result = await remove_preference(
                "nonexistent@example.com", "megatrend-folger"
            )

            # Verify
            assert result is False
            mock_mongodb_service.close.assert_called_once()

    async def test_remove_preference_not_found(
        self, mock_mongodb_service, sample_recipient
    ):
        """Test removing preference that doesn't exist."""
        with patch(
            "manage_recipient_preferences.get_mongodb_service",
            return_value=mock_mongodb_service,
        ):
            # Setup mocks
            mock_mongodb_service.db.recipients.find_one = AsyncMock(
                return_value=sample_recipient
            )

            # Execute (trying to remove nonexistent preference)
            result = await remove_preference("user@example.com", "nonexistent-pub")

            # Verify
            assert result is False
            mock_mongodb_service.close.assert_called_once()


@pytest.mark.asyncio
class TestListPreferences:
    """Tests for list_preferences function."""

    async def test_list_preferences_success(
        self, mock_mongodb_service, sample_recipient, capsys
    ):
        """Test listing preferences for a recipient."""
        with patch(
            "manage_recipient_preferences.get_mongodb_service",
            return_value=mock_mongodb_service,
        ):
            # Setup mocks
            mock_mongodb_service.db.recipients.find_one = AsyncMock(
                return_value=sample_recipient
            )
            mock_mongodb_service.get_publications.return_value = [
                {"publication_id": "megatrend-folger", "name": "Megatrend Folger"}
            ]

            # Execute
            await list_preferences("user@example.com")

            # Verify output contains key information
            captured = capsys.readouterr()
            assert "user@example.com" in captured.out
            assert "Megatrend Folger" in captured.out
            mock_mongodb_service.close.assert_called_once()

    async def test_list_preferences_recipient_not_found(self, mock_mongodb_service):
        """Test listing preferences when recipient doesn't exist."""
        with patch(
            "manage_recipient_preferences.get_mongodb_service",
            return_value=mock_mongodb_service,
        ):
            # Setup mocks
            mock_mongodb_service.db.recipients.find_one = AsyncMock(return_value=None)

            # Execute
            await list_preferences("nonexistent@example.com")

            # Verify
            mock_mongodb_service.close.assert_called_once()

    async def test_list_preferences_no_preferences(self, mock_mongodb_service, capsys):
        """Test listing preferences when recipient has none."""
        with patch(
            "manage_recipient_preferences.get_mongodb_service",
            return_value=mock_mongodb_service,
        ):
            # Setup mocks
            recipient = {
                "email": "user@example.com",
                "active": True,
                "publication_preferences": [],
            }
            mock_mongodb_service.db.recipients.find_one = AsyncMock(
                return_value=recipient
            )

            # Execute
            await list_preferences("user@example.com")

            # Verify output
            captured = capsys.readouterr()
            assert "No preferences configured" in captured.out
            mock_mongodb_service.close.assert_called_once()


@pytest.mark.asyncio
class TestBulkOperations:
    """Tests for bulk add/remove operations."""

    async def test_bulk_add_preference_success(
        self, mock_mongodb_service, sample_publication
    ):
        """Test bulk adding preference to all recipients."""
        with patch(
            "manage_recipient_preferences.get_mongodb_service",
            return_value=mock_mongodb_service,
        ):
            # Setup mocks
            mock_mongodb_service.db.publications.find_one = AsyncMock(
                return_value=sample_publication
            )
            # Mock find() to return a cursor mock with to_list method
            mock_cursor = MagicMock()
            mock_cursor.to_list = AsyncMock(
                return_value=[
                    {
                        "email": "user1@example.com",
                        "active": True,
                        "publication_preferences": [],
                    },
                    {
                        "email": "user2@example.com",
                        "active": True,
                        "publication_preferences": [],
                    },
                ]
            )
            mock_mongodb_service.db.recipients.find = MagicMock(
                return_value=mock_cursor
            )
            mock_mongodb_service.db.recipients.update_one = AsyncMock(
                return_value=MagicMock(modified_count=1)
            )

            # Execute
            result = await bulk_add_preference("aktionaer-epaper")

            # Verify
            assert result is True
            assert mock_mongodb_service.db.recipients.update_one.call_count == 2
            mock_mongodb_service.close.assert_called_once()

    async def test_bulk_add_preference_publication_not_found(
        self, mock_mongodb_service
    ):
        """Test bulk add when publication doesn't exist."""
        with patch(
            "manage_recipient_preferences.get_mongodb_service",
            return_value=mock_mongodb_service,
        ):
            # Setup mocks
            mock_mongodb_service.db.publications.find_one = AsyncMock(return_value=None)

            # Execute
            result = await bulk_add_preference("nonexistent-pub")

            # Verify
            assert result is False
            mock_mongodb_service.close.assert_called_once()

    async def test_bulk_remove_preference_success(
        self, mock_mongodb_service, sample_publication
    ):
        """Test bulk removing preference from all recipients."""
        with patch(
            "manage_recipient_preferences.get_mongodb_service",
            return_value=mock_mongodb_service,
        ):
            # Setup mocks
            mock_mongodb_service.db.publications.find_one = AsyncMock(
                return_value=sample_publication
            )
            # Mock find() to return a cursor mock with to_list method
            mock_cursor = MagicMock()
            mock_cursor.to_list = AsyncMock(
                return_value=[
                    {
                        "email": "user1@example.com",
                        "publication_preferences": [
                            {"publication_id": "aktionaer-epaper"}
                        ],
                    },
                    {
                        "email": "user2@example.com",
                        "publication_preferences": [
                            {"publication_id": "aktionaer-epaper"}
                        ],
                    },
                ]
            )
            mock_mongodb_service.db.recipients.find = MagicMock(
                return_value=mock_cursor
            )
            mock_mongodb_service.db.recipients.update_one = AsyncMock(
                return_value=MagicMock(modified_count=1)
            )

            # Execute
            result = await bulk_remove_preference("aktionaer-epaper")

            # Verify
            assert result is True
            assert mock_mongodb_service.db.recipients.update_one.call_count == 2
            mock_mongodb_service.close.assert_called_once()


@pytest.mark.asyncio
class TestShowStatistics:
    """Tests for show_statistics function."""

    async def test_show_statistics_success(self, mock_mongodb_service, capsys):
        """Test showing preference statistics."""
        with patch(
            "manage_recipient_preferences.get_mongodb_service",
            return_value=mock_mongodb_service,
        ):
            # Setup mocks
            mock_cursor = MagicMock()
            mock_cursor.to_list = AsyncMock(
                return_value=[
                    {
                        "email": "user1@example.com",
                        "active": True,
                        "publication_preferences": [
                            {
                                "publication_id": "megatrend-folger",
                                "enabled": True,
                                "email_enabled": True,
                                "upload_enabled": True,
                            }
                        ],
                    },
                    {
                        "email": "user2@example.com",
                        "active": True,
                        "publication_preferences": [],
                    },
                ]
            )
            mock_mongodb_service.db.recipients.find = MagicMock(
                return_value=mock_cursor
            )
            mock_mongodb_service.get_publications.return_value = [
                {
                    "publication_id": "megatrend-folger",
                    "name": "Megatrend Folger",
                    "active": True,
                }
            ]

            # Execute
            await show_statistics()

            # Verify output contains key statistics
            captured = capsys.readouterr()
            assert "PREFERENCE STATISTICS" in captured.out
            assert "Per-Publication Coverage" in captured.out
            assert "Delivery Method Statistics" in captured.out
            mock_mongodb_service.close.assert_called_once()

    async def test_show_statistics_no_recipients(self, mock_mongodb_service):
        """Test statistics when no recipients exist."""
        with patch(
            "manage_recipient_preferences.get_mongodb_service",
            return_value=mock_mongodb_service,
        ):
            # Setup mocks
            mock_cursor = MagicMock()
            mock_cursor.to_list = AsyncMock(return_value=[])
            mock_mongodb_service.db.recipients.find = MagicMock(
                return_value=mock_cursor
            )

            # Execute
            await show_statistics()

            # Verify
            mock_mongodb_service.close.assert_called_once()
