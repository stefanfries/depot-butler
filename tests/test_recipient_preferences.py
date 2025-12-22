"""
Tests for recipient preference queries and per-publication filtering.

Tests cover:
- get_recipients_for_publication() with various preference scenarios
- folder resolution logic (custom vs default)
- organize_by_year resolution logic (recipient override vs publication default)
- per-publication tracking (send_count, last_sent_at)
- backward compatibility (empty preferences = receive all)
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from depotbutler.db.mongodb import MongoDBService


@pytest.fixture
def mongodb_service():
    """Create a MongoDBService instance for testing."""
    service = MongoDBService()
    service._connected = True
    service.db = MagicMock()
    return service


@pytest.fixture
def sample_publication():
    """Sample publication document."""
    return {
        "publication_id": "megatrend-folger",
        "name": "Megatrend Folger",
        "default_onedrive_folder": "/Dokumente/Banken/Megatrend",
        "organize_by_year": True,
        "email_enabled": True,
        "onedrive_enabled": True,
    }


@pytest.fixture
def sample_recipients():
    """Sample recipient documents with various preference scenarios."""
    return [
        # Recipient with no preferences (should receive all publications)
        {
            "email": "no-prefs@example.com",
            "first_name": "NoPrefs",
            "active": True,
            "publication_preferences": [],
        },
        # Recipient with email enabled for this publication
        {
            "email": "email-only@example.com",
            "first_name": "EmailOnly",
            "active": True,
            "publication_preferences": [
                {
                    "publication_id": "megatrend-folger",
                    "enabled": True,
                    "email_enabled": True,
                    "upload_enabled": False,
                    "custom_onedrive_folder": None,
                    "organize_by_year": None,
                    "send_count": 5,
                    "last_sent_at": datetime(2025, 12, 1, 10, 0, 0, tzinfo=UTC),
                }
            ],
        },
        # Recipient with upload enabled and custom folder
        {
            "email": "upload-custom@example.com",
            "first_name": "UploadCustom",
            "active": True,
            "publication_preferences": [
                {
                    "publication_id": "megatrend-folger",
                    "enabled": True,
                    "email_enabled": False,
                    "upload_enabled": True,
                    "custom_onedrive_folder": "/My/Custom/Folder",
                    "organize_by_year": False,
                    "send_count": 10,
                    "last_sent_at": datetime(2025, 12, 10, 15, 30, 0, tzinfo=UTC),
                }
            ],
        },
        # Recipient with both methods enabled and organize_by_year override
        {
            "email": "both-methods@example.com",
            "first_name": "BothMethods",
            "active": True,
            "publication_preferences": [
                {
                    "publication_id": "megatrend-folger",
                    "enabled": True,
                    "email_enabled": True,
                    "upload_enabled": True,
                    "custom_onedrive_folder": "/Shared/Folder",
                    "organize_by_year": True,
                    "send_count": 3,
                    "last_sent_at": datetime(2025, 12, 14, 8, 0, 0, tzinfo=UTC),
                }
            ],
        },
        # Recipient with preference for different publication
        {
            "email": "other-pub@example.com",
            "first_name": "OtherPub",
            "active": True,
            "publication_preferences": [
                {
                    "publication_id": "other-publication",
                    "enabled": True,
                    "email_enabled": True,
                    "upload_enabled": False,
                    "custom_onedrive_folder": None,
                    "organize_by_year": None,
                    "send_count": 0,
                    "last_sent_at": None,
                }
            ],
        },
        # Inactive recipient (should never be returned)
        {
            "email": "inactive@example.com",
            "first_name": "Inactive",
            "active": False,
            "publication_preferences": [
                {
                    "publication_id": "megatrend-folger",
                    "enabled": True,
                    "email_enabled": True,
                    "upload_enabled": True,
                    "custom_onedrive_folder": None,
                    "organize_by_year": None,
                    "send_count": 0,
                    "last_sent_at": None,
                }
            ],
        },
    ]


class TestGetRecipientsForPublication:
    """Tests for get_recipients_for_publication query function."""

    @pytest.mark.asyncio
    async def test_get_recipients_email_method(
        self, mongodb_service, sample_recipients
    ):
        """Test getting recipients with email enabled for a publication."""
        expected_recipients = [
            sample_recipients[1],  # email-only
            sample_recipients[3],  # both-methods
        ]

        mock_repo = AsyncMock()
        mock_repo.get_recipients_for_publication = AsyncMock(
            return_value=expected_recipients
        )

        mongodb_service.recipient_repo = mock_repo
        mongodb_service._connected = True

        # Execute
        recipients = await mongodb_service.get_recipients_for_publication(
            "megatrend-folger", "email"
        )

        # Verify - only recipients with explicit preferences
        assert len(recipients) == 2
        assert recipients[0]["email"] == "email-only@example.com"
        assert recipients[1]["email"] == "both-methods@example.com"

        mock_repo.get_recipients_for_publication.assert_called_once_with(
            "megatrend-folger", "email"
        )

    @pytest.mark.asyncio
    async def test_get_recipients_upload_method(
        self, mongodb_service, sample_recipients
    ):
        """Test getting recipients with upload enabled for a publication."""
        expected_recipients = [
            sample_recipients[2],  # upload-custom
            sample_recipients[3],  # both-methods
        ]

        mock_repo = AsyncMock()
        mock_repo.get_recipients_for_publication = AsyncMock(
            return_value=expected_recipients
        )

        mongodb_service.recipient_repo = mock_repo
        mongodb_service._connected = True

        # Execute
        recipients = await mongodb_service.get_recipients_for_publication(
            "megatrend-folger", "upload"
        )

        # Verify - only recipients with explicit preferences
        assert len(recipients) == 2
        assert recipients[0]["email"] == "upload-custom@example.com"
        assert recipients[1]["email"] == "both-methods@example.com"

        mock_repo.get_recipients_for_publication.assert_called_once_with(
            "megatrend-folger", "upload"
        )

    @pytest.mark.asyncio
    async def test_empty_preferences_receive_nothing(
        self, mongodb_service, sample_recipients
    ):
        """Test that recipients with no preferences receive NOTHING (opt-in model)."""
        mock_repo = AsyncMock()
        mock_repo.get_recipients_for_publication = AsyncMock(return_value=[])

        mongodb_service.recipient_repo = mock_repo
        mongodb_service._connected = True

        recipients = await mongodb_service.get_recipients_for_publication(
            "any-publication", "email"
        )

        # No recipients should match - empty preferences = receive nothing
        assert len(recipients) == 0
        mock_repo.get_recipients_for_publication.assert_called_once_with(
            "any-publication", "email"
        )

    @pytest.mark.asyncio
    async def test_invalid_delivery_method(self, mongodb_service):
        """Test that invalid delivery method returns empty list."""
        mock_repo = AsyncMock()
        mock_repo.get_recipients_for_publication = AsyncMock(return_value=[])

        mongodb_service.recipient_repo = mock_repo
        mongodb_service._connected = True

        recipients = await mongodb_service.get_recipients_for_publication(
            "megatrend-folger", "invalid"
        )

        assert recipients == []

    @pytest.mark.asyncio
    async def test_no_matching_recipients(self, mongodb_service):
        """Test when no recipients match the criteria."""
        mock_repo = AsyncMock()
        mock_repo.get_recipients_for_publication = AsyncMock(return_value=[])

        mongodb_service.recipient_repo = mock_repo
        mongodb_service._connected = True

        recipients = await mongodb_service.get_recipients_for_publication(
            "unknown-publication", "email"
        )

        assert recipients == []
        mock_repo.get_recipients_for_publication.assert_called_once_with(
            "unknown-publication", "email"
        )


class TestFolderResolution:
    """Tests for OneDrive folder resolution logic."""

    def test_custom_folder_takes_priority(
        self, mongodb_service, sample_publication, sample_recipients
    ):
        """Test that recipient's custom folder takes priority over publication default."""
        recipient = sample_recipients[2]  # upload-custom

        mock_repo = MagicMock()
        mock_repo.get_onedrive_folder_for_recipient = MagicMock(
            return_value="/My/Custom/Folder"
        )

        mongodb_service.recipient_repo = mock_repo

        folder = mongodb_service.get_onedrive_folder_for_recipient(
            recipient, sample_publication
        )

        assert folder == "/My/Custom/Folder"
        mock_repo.get_onedrive_folder_for_recipient.assert_called_once_with(
            recipient, sample_publication
        )

    def test_fallback_to_publication_default(
        self, mongodb_service, sample_publication, sample_recipients
    ):
        """Test fallback to publication default when no custom folder."""
        recipient = sample_recipients[1]  # email-only (no custom folder)

        mock_repo = MagicMock()
        mock_repo.get_onedrive_folder_for_recipient = MagicMock(
            return_value="/Dokumente/Banken/Megatrend"
        )

        mongodb_service.recipient_repo = mock_repo

        folder = mongodb_service.get_onedrive_folder_for_recipient(
            recipient, sample_publication
        )

        assert folder == "/Dokumente/Banken/Megatrend"
        mock_repo.get_onedrive_folder_for_recipient.assert_called_once_with(
            recipient, sample_publication
        )

    def test_no_preferences_uses_default(
        self, mongodb_service, sample_publication, sample_recipients
    ):
        """Test that recipient with no preferences uses publication default."""
        recipient = sample_recipients[0]  # no-prefs

        mock_repo = MagicMock()
        mock_repo.get_onedrive_folder_for_recipient = MagicMock(
            return_value="/Dokumente/Banken/Megatrend"
        )

        mongodb_service.recipient_repo = mock_repo

        folder = mongodb_service.get_onedrive_folder_for_recipient(
            recipient, sample_publication
        )

        assert folder == "/Dokumente/Banken/Megatrend"
        mock_repo.get_onedrive_folder_for_recipient.assert_called_once_with(
            recipient, sample_publication
        )

    def test_empty_default_folder(self, mongodb_service, sample_recipients):
        """Test behavior when publication has no default folder."""
        publication = {
            "publication_id": "test-pub",
            "default_onedrive_folder": "",
        }
        recipient = sample_recipients[0]

        mock_repo = MagicMock()
        mock_repo.get_onedrive_folder_for_recipient = MagicMock(return_value="")

        mongodb_service.recipient_repo = mock_repo

        folder = mongodb_service.get_onedrive_folder_for_recipient(
            recipient, publication
        )

        assert folder == ""
        mock_repo.get_onedrive_folder_for_recipient.assert_called_once_with(
            recipient, publication
        )


class TestOrganizeByYearResolution:
    """Tests for organize_by_year resolution logic."""

    def test_recipient_override_false(
        self, mongodb_service, sample_publication, sample_recipients
    ):
        """Test recipient override set to False takes priority."""
        recipient = sample_recipients[2]  # organize_by_year: False

        mock_repo = MagicMock()
        mock_repo.get_organize_by_year_for_recipient = MagicMock(return_value=False)

        mongodb_service.recipient_repo = mock_repo

        organize = mongodb_service.get_organize_by_year_for_recipient(
            recipient, sample_publication
        )

        assert organize is False
        mock_repo.get_organize_by_year_for_recipient.assert_called_once_with(
            recipient, sample_publication
        )

    def test_recipient_override_true(
        self, mongodb_service, sample_publication, sample_recipients
    ):
        """Test recipient override set to True takes priority."""
        recipient = sample_recipients[3]  # organize_by_year: True

        mock_repo = MagicMock()
        mock_repo.get_organize_by_year_for_recipient = MagicMock(return_value=True)

        mongodb_service.recipient_repo = mock_repo

        organize = mongodb_service.get_organize_by_year_for_recipient(
            recipient, sample_publication
        )

        assert organize is True
        mock_repo.get_organize_by_year_for_recipient.assert_called_once_with(
            recipient, sample_publication
        )

    def test_fallback_to_publication_setting(
        self, mongodb_service, sample_publication, sample_recipients
    ):
        """Test fallback to publication setting when recipient has no override."""
        recipient = sample_recipients[1]  # organize_by_year: None

        mock_repo = MagicMock()
        mock_repo.get_organize_by_year_for_recipient = MagicMock(return_value=True)

        mongodb_service.recipient_repo = mock_repo

        organize = mongodb_service.get_organize_by_year_for_recipient(
            recipient, sample_publication
        )

        assert organize is True  # Publication default
        mock_repo.get_organize_by_year_for_recipient.assert_called_once_with(
            recipient, sample_publication
        )

    def test_default_to_true_when_not_set(self, mongodb_service, sample_recipients):
        """Test default to True when neither recipient nor publication specify."""
        publication = {"publication_id": "test-pub"}  # No organize_by_year
        recipient = sample_recipients[0]  # No preferences

        mock_repo = MagicMock()
        mock_repo.get_organize_by_year_for_recipient = MagicMock(return_value=True)

        mongodb_service.recipient_repo = mock_repo

        organize = mongodb_service.get_organize_by_year_for_recipient(
            recipient, publication
        )

        assert organize is True
        mock_repo.get_organize_by_year_for_recipient.assert_called_once_with(
            recipient, publication
        )

    def test_publication_setting_false(self, mongodb_service, sample_recipients):
        """Test publication setting of False is respected."""
        publication = {
            "publication_id": "test-pub",
            "organize_by_year": False,
        }
        recipient = sample_recipients[0]  # No preferences

        mock_repo = MagicMock()
        mock_repo.get_organize_by_year_for_recipient = MagicMock(return_value=False)

        mongodb_service.recipient_repo = mock_repo

        organize = mongodb_service.get_organize_by_year_for_recipient(
            recipient, publication
        )

        assert organize is False
        mock_repo.get_organize_by_year_for_recipient.assert_called_once_with(
            recipient, publication
        )


class TestPerPublicationTracking:
    """Tests for per-publication send tracking."""

    @pytest.mark.asyncio
    async def test_update_stats_with_publication_id(self, mongodb_service):
        """Test updating per-publication stats."""
        mock_repo = AsyncMock()
        mock_repo.update_recipient_stats = AsyncMock()

        mongodb_service.recipient_repo = mock_repo
        mongodb_service._connected = True

        await mongodb_service.update_recipient_stats(
            "test@example.com", "megatrend-folger"
        )

        mock_repo.update_recipient_stats.assert_called_once_with(
            "test@example.com", "megatrend-folger"
        )

    @pytest.mark.asyncio
    async def test_update_stats_legacy_mode(self, mongodb_service):
        """Test updating global stats (legacy mode) when no publication_id."""
        mock_repo = AsyncMock()
        mock_repo.update_recipient_stats = AsyncMock()

        mongodb_service.recipient_repo = mock_repo
        mongodb_service._connected = True

        await mongodb_service.update_recipient_stats("test@example.com", None)

        mock_repo.update_recipient_stats.assert_called_once_with(
            "test@example.com", None
        )

    @pytest.mark.asyncio
    async def test_update_stats_recipient_not_found(self, mongodb_service):
        """Test behavior when recipient not found in database."""
        mock_repo = AsyncMock()
        mock_repo.update_recipient_stats = AsyncMock()

        mongodb_service.recipient_repo = mock_repo
        mongodb_service._connected = True

        # Should not raise exception
        await mongodb_service.update_recipient_stats(
            "nonexistent@example.com", "megatrend-folger"
        )

        # Verify it attempted the update
        mock_repo.update_recipient_stats.assert_called_once_with(
            "nonexistent@example.com", "megatrend-folger"
        )


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_get_recipients_database_error(self, mongodb_service):
        """Test handling of database errors."""
        mock_repo = AsyncMock()
        # The repo should handle the exception and return empty list, not raise
        mock_repo.get_recipients_for_publication = AsyncMock(return_value=[])

        mongodb_service.recipient_repo = mock_repo
        mongodb_service._connected = True

        recipients = await mongodb_service.get_recipients_for_publication(
            "megatrend-folger", "email"
        )

        assert recipients == []

    @pytest.mark.asyncio
    async def test_update_stats_database_error(self, mongodb_service):
        """Test handling of database errors during stat updates."""
        mock_repo = AsyncMock()
        # The repo should handle the exception silently (no return value)
        mock_repo.update_recipient_stats = AsyncMock()

        mongodb_service.recipient_repo = mock_repo
        mongodb_service._connected = True

        # Should not raise exception
        await mongodb_service.update_recipient_stats(
            "test@example.com", "megatrend-folger"
        )

    def test_folder_resolution_missing_publication_id(
        self, mongodb_service, sample_recipients
    ):
        """Test folder resolution when publication_id is missing."""
        recipient = sample_recipients[3]  # Has preference
        publication = {"publication_id": "different-pub"}

        mock_repo = MagicMock()
        mock_repo.get_onedrive_folder_for_recipient = MagicMock(return_value="")

        mongodb_service.recipient_repo = mock_repo

        folder = mongodb_service.get_onedrive_folder_for_recipient(
            recipient, publication
        )

        # Should fallback to publication default (empty in this case)
        assert folder == ""
        mock_repo.get_onedrive_folder_for_recipient.assert_called_once_with(
            recipient, publication
        )
