"""Tests for publication discovery and synchronization service.

This test module covers:
- Discovery of new publications from account
- Updating existing publications with latest data
- Sync result tracking and error handling
- Edge cases and failure scenarios
"""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, patch

import pytest

from depotbutler.httpx_client import HttpxBoersenmedienClient
from depotbutler.models import Subscription
from depotbutler.services.publication_discovery_service import (
    PublicationDiscoveryService,
)


@pytest.fixture
def mock_httpx_client() -> AsyncMock:
    """Create a mock HTTP client for testing."""
    client = AsyncMock(spec=HttpxBoersenmedienClient)
    return client


@pytest.fixture
def discovery_service(mock_httpx_client: AsyncMock) -> PublicationDiscoveryService:
    """Create discovery service with mocked HTTP client."""
    return PublicationDiscoveryService(mock_httpx_client)


@pytest.fixture
def sample_subscriptions() -> list[Subscription]:
    """Sample subscriptions returned from account discovery."""
    return [
        Subscription(
            name="Megatrend Folger",
            subscription_id="megatrend-folger",
            subscription_number="123456",
            content_url="https://example.com/megatrend",
            subscription_type="Megatrend Folger",
            duration="01.01.2024 - 31.12.2024",
            duration_start=date(2024, 1, 1),
            duration_end=date(2024, 12, 31),
        ),
        Subscription(
            name="DER AKTIONÄR E-Paper",
            subscription_id="der-aktionaer-epaper",
            subscription_number="789012",
            content_url="https://example.com/der-aktionaer",
            subscription_type="DER AKTIONÄR E-Paper",
            duration="01.06.2024 - 31.05.2025",
            duration_start=date(2024, 6, 1),
            duration_end=date(2025, 5, 31),
        ),
    ]


@pytest.fixture
def existing_publication() -> dict:
    """Sample existing publication in database."""
    return {
        "publication_id": "megatrend-folger",
        "name": "Megatrend Folger",
        "subscription_id": "megatrend-folger",
        "subscription_number": "123456",
        "subscription_type": "Megatrend Folger",
        "duration": "01.01.2024 - 31.12.2024",
        "active": True,
        "discovered": True,
        "first_discovered": datetime(2024, 1, 1, tzinfo=UTC),
        "last_seen": datetime(2024, 6, 1, tzinfo=UTC),
        "email_enabled": True,
        "onedrive_enabled": True,
    }


# ============================================================================
# Test: Discovery of New Publications
# ============================================================================


@pytest.mark.asyncio
async def test_sync_creates_new_publication(
    discovery_service: PublicationDiscoveryService,
    mock_httpx_client: AsyncMock,
    sample_subscriptions: list[Subscription],
) -> None:
    """Test that newly discovered subscriptions create new publications."""
    # Setup: No existing publications
    mock_httpx_client.discover_subscriptions.return_value = [sample_subscriptions[0]]

    with (
        patch(
            "depotbutler.services.publication_discovery_service.get_publications",
            new_callable=AsyncMock,
        ) as mock_get_pubs,
        patch(
            "depotbutler.services.publication_discovery_service.create_publication",
            new_callable=AsyncMock,
        ) as mock_create,
    ):
        mock_get_pubs.return_value = []
        mock_create.return_value = True

        # Execute
        result = await discovery_service.sync_publications_from_account()

        # Verify
        assert result["discovered_count"] == 1
        assert result["new_count"] == 1
        assert result["updated_count"] == 0
        assert len(result["errors"]) == 0

        # Verify create_publication was called with correct data
        mock_create.assert_called_once()
        call_args = mock_create.call_args[0][0]
        assert call_args["publication_id"] == "megatrend-folger"
        assert call_args["name"] == "Megatrend Folger"
        assert call_args["subscription_id"] == "megatrend-folger"
        assert call_args["subscription_number"] == "123456"
        assert call_args["active"] is True
        assert call_args["discovered"] is True
        assert call_args["email_enabled"] is False  # Default disabled
        assert call_args["onedrive_enabled"] is False  # Default disabled


@pytest.mark.asyncio
async def test_sync_creates_multiple_new_publications(
    discovery_service: PublicationDiscoveryService,
    mock_httpx_client: AsyncMock,
    sample_subscriptions: list[Subscription],
) -> None:
    """Test that multiple new subscriptions all get created."""
    # Setup: Multiple subscriptions, no existing publications
    mock_httpx_client.discover_subscriptions.return_value = sample_subscriptions

    with (
        patch(
            "depotbutler.services.publication_discovery_service.get_publications",
            new_callable=AsyncMock,
        ) as mock_get_pubs,
        patch(
            "depotbutler.services.publication_discovery_service.create_publication",
            new_callable=AsyncMock,
        ) as mock_create,
    ):
        mock_get_pubs.return_value = []
        mock_create.return_value = True

        # Execute
        result = await discovery_service.sync_publications_from_account()

        # Verify
        assert result["discovered_count"] == 2
        assert result["new_count"] == 2
        assert result["updated_count"] == 0
        assert len(result["errors"]) == 0
        assert mock_create.call_count == 2


# ============================================================================
# Test: Updating Existing Publications
# ============================================================================


@pytest.mark.asyncio
async def test_sync_updates_existing_publication(
    discovery_service: PublicationDiscoveryService,
    mock_httpx_client: AsyncMock,
    sample_subscriptions: list[Subscription],
    existing_publication: dict,
) -> None:
    """Test that existing publications get updated with latest data."""
    # Setup: One subscription matches existing publication
    mock_httpx_client.discover_subscriptions.return_value = [sample_subscriptions[0]]

    with (
        patch(
            "depotbutler.services.publication_discovery_service.get_publications",
            new_callable=AsyncMock,
        ) as mock_get_pubs,
        patch(
            "depotbutler.services.publication_discovery_service.update_publication",
            new_callable=AsyncMock,
        ) as mock_update,
    ):
        mock_get_pubs.return_value = [existing_publication]
        mock_update.return_value = True

        # Execute
        result = await discovery_service.sync_publications_from_account()

        # Verify
        assert result["discovered_count"] == 1
        assert result["new_count"] == 0
        assert result["updated_count"] == 1
        assert len(result["errors"]) == 0

        # Verify update_publication was called
        mock_update.assert_called_once()
        pub_id, update_data = mock_update.call_args[0]
        assert pub_id == "megatrend-folger"
        assert "last_seen" in update_data
        assert update_data["subscription_number"] == "123456"
        assert update_data["subscription_type"] == "Megatrend Folger"


@pytest.mark.asyncio
async def test_sync_marks_manual_publication_as_discovered(
    discovery_service: PublicationDiscoveryService,
    mock_httpx_client: AsyncMock,
    sample_subscriptions: list[Subscription],
    existing_publication: dict,
) -> None:
    """Test that manually created publications get marked as discovered."""
    # Setup: Existing publication was manually created (not discovered)
    manual_publication = existing_publication.copy()
    manual_publication["discovered"] = False
    manual_publication.pop("first_discovered", None)

    mock_httpx_client.discover_subscriptions.return_value = [sample_subscriptions[0]]

    with (
        patch(
            "depotbutler.services.publication_discovery_service.get_publications",
            new_callable=AsyncMock,
        ) as mock_get_pubs,
        patch(
            "depotbutler.services.publication_discovery_service.update_publication",
            new_callable=AsyncMock,
        ) as mock_update,
    ):
        mock_get_pubs.return_value = [manual_publication]
        mock_update.return_value = True

        # Execute
        await discovery_service.sync_publications_from_account()

        # Verify publication marked as discovered
        mock_update.assert_called_once()
        pub_id, update_data = mock_update.call_args[0]
        assert update_data["discovered"] is True
        assert "first_discovered" in update_data
        assert isinstance(update_data["first_discovered"], datetime)


@pytest.mark.asyncio
async def test_sync_mixed_new_and_existing(
    discovery_service: PublicationDiscoveryService,
    mock_httpx_client: AsyncMock,
    sample_subscriptions: list[Subscription],
    existing_publication: dict,
) -> None:
    """Test syncing with mix of new and existing subscriptions."""
    # Setup: First subscription exists, second is new
    mock_httpx_client.discover_subscriptions.return_value = sample_subscriptions

    with (
        patch(
            "depotbutler.services.publication_discovery_service.get_publications",
            new_callable=AsyncMock,
        ) as mock_get_pubs,
        patch(
            "depotbutler.services.publication_discovery_service.update_publication",
            new_callable=AsyncMock,
        ) as mock_update,
        patch(
            "depotbutler.services.publication_discovery_service.create_publication",
            new_callable=AsyncMock,
        ) as mock_create,
    ):
        mock_get_pubs.return_value = [existing_publication]
        mock_update.return_value = True
        mock_create.return_value = True

        # Execute
        result = await discovery_service.sync_publications_from_account()

        # Verify
        assert result["discovered_count"] == 2
        assert result["new_count"] == 1  # der-aktionaer-epaper
        assert result["updated_count"] == 1  # megatrend-folger
        assert len(result["errors"]) == 0


# ============================================================================
# Test: Edge Cases
# ============================================================================


@pytest.mark.asyncio
async def test_sync_no_subscriptions_found(
    discovery_service: PublicationDiscoveryService,
    mock_httpx_client: AsyncMock,
) -> None:
    """Test sync when no subscriptions are discovered from account."""
    # Setup: Empty subscription list
    mock_httpx_client.discover_subscriptions.return_value = []

    with (
        patch(
            "depotbutler.services.publication_discovery_service.get_publications",
            new_callable=AsyncMock,
        ) as mock_get_pubs,
        patch(
            "depotbutler.services.publication_discovery_service.create_publication",
            new_callable=AsyncMock,
        ) as mock_create,
        patch(
            "depotbutler.services.publication_discovery_service.update_publication",
            new_callable=AsyncMock,
        ) as mock_update,
    ):
        mock_get_pubs.return_value = []

        # Execute
        result = await discovery_service.sync_publications_from_account()

        # Verify
        assert result["discovered_count"] == 0
        assert result["new_count"] == 0
        assert result["updated_count"] == 0
        assert len(result["errors"]) == 0

        # Verify no database operations
        mock_create.assert_not_called()
        mock_update.assert_not_called()


@pytest.mark.asyncio
async def test_sync_handles_subscription_without_duration_dates(
    discovery_service: PublicationDiscoveryService,
    mock_httpx_client: AsyncMock,
) -> None:
    """Test sync handles subscriptions without duration_start/end dates."""
    # Setup: Subscription with no dates
    subscription = Subscription(
        name="Test Publication",
        subscription_id="test-pub",
        subscription_number="999999",
        content_url="https://example.com/test",
        subscription_type="Test Publication",
        duration="Unbegrenzt",
        duration_start=None,
        duration_end=None,
    )

    mock_httpx_client.discover_subscriptions.return_value = [subscription]

    with (
        patch(
            "depotbutler.services.publication_discovery_service.get_publications",
            new_callable=AsyncMock,
        ) as mock_get_pubs,
        patch(
            "depotbutler.services.publication_discovery_service.create_publication",
            new_callable=AsyncMock,
        ) as mock_create,
    ):
        mock_get_pubs.return_value = []
        mock_create.return_value = True

        # Execute
        result = await discovery_service.sync_publications_from_account()

        # Verify no errors
        assert result["new_count"] == 1
        assert len(result["errors"]) == 0

        # Verify publication created without date fields
        call_args = mock_create.call_args[0][0]
        assert (
            "duration_start" not in call_args or call_args.get("duration_start") is None
        )
        assert "duration_end" not in call_args or call_args.get("duration_end") is None


# ============================================================================
# Test: Error Handling
# ============================================================================


@pytest.mark.asyncio
async def test_sync_handles_create_failure_gracefully(
    discovery_service: PublicationDiscoveryService,
    mock_httpx_client: AsyncMock,
    sample_subscriptions: list[Subscription],
) -> None:
    """Test that create failure for one subscription doesn't stop others."""
    # Setup: Two subscriptions, first fails to create
    mock_httpx_client.discover_subscriptions.return_value = sample_subscriptions

    with (
        patch(
            "depotbutler.services.publication_discovery_service.get_publications",
            new_callable=AsyncMock,
        ) as mock_get_pubs,
        patch(
            "depotbutler.services.publication_discovery_service.create_publication",
            new_callable=AsyncMock,
        ) as mock_create,
    ):
        mock_get_pubs.return_value = []
        mock_create.side_effect = [
            Exception("Database error"),  # First fails
            True,  # Second succeeds
        ]

        # Execute
        result = await discovery_service.sync_publications_from_account()

        # Verify: One succeeded, one failed
        assert result["discovered_count"] == 2
        assert result["new_count"] == 1  # One succeeded
        assert len(result["errors"]) == 1
        assert "Failed to process subscription" in result["errors"][0]


@pytest.mark.asyncio
async def test_sync_handles_update_failure_gracefully(
    discovery_service: PublicationDiscoveryService,
    mock_httpx_client: AsyncMock,
    sample_subscriptions: list[Subscription],
) -> None:
    """Test that update failure is handled gracefully."""
    # Setup: Existing publication, update fails
    existing = {
        "publication_id": "megatrend-folger",
        "subscription_id": "megatrend-folger",
        "discovered": True,
    }

    mock_httpx_client.discover_subscriptions.return_value = [sample_subscriptions[0]]

    with (
        patch(
            "depotbutler.services.publication_discovery_service.get_publications",
            new_callable=AsyncMock,
        ) as mock_get_pubs,
        patch(
            "depotbutler.services.publication_discovery_service.update_publication",
            new_callable=AsyncMock,
        ) as mock_update,
    ):
        mock_get_pubs.return_value = [existing]
        mock_update.return_value = False  # Simulate failure

        # Execute
        result = await discovery_service.sync_publications_from_account()

        # Verify error recorded
        assert len(result["errors"]) == 1
        assert "Failed to update publication" in result["errors"][0]


@pytest.mark.asyncio
async def test_sync_propagates_discovery_failure(
    discovery_service: PublicationDiscoveryService,
    mock_httpx_client: AsyncMock,
) -> None:
    """Test that complete discovery failure propagates exception."""
    # Setup: discover_subscriptions raises exception
    mock_httpx_client.discover_subscriptions.side_effect = Exception("Network failure")

    # Execute and verify exception propagates
    with pytest.raises(Exception, match="Network failure"):
        await discovery_service.sync_publications_from_account()


# ============================================================================
# Test: Duration Date Handling
# ============================================================================


@pytest.mark.asyncio
async def test_sync_creates_publication_with_duration_dates(
    discovery_service: PublicationDiscoveryService,
    mock_httpx_client: AsyncMock,
    sample_subscriptions: list[Subscription],
) -> None:
    """Test that duration dates are properly converted and stored."""
    # Setup
    subscription = sample_subscriptions[0]  # Has duration dates
    mock_httpx_client.discover_subscriptions.return_value = [subscription]

    with (
        patch(
            "depotbutler.services.publication_discovery_service.get_publications",
            new_callable=AsyncMock,
        ) as mock_get_pubs,
        patch(
            "depotbutler.services.publication_discovery_service.create_publication",
            new_callable=AsyncMock,
        ) as mock_create,
    ):
        mock_get_pubs.return_value = []
        mock_create.return_value = True

        # Execute
        await discovery_service.sync_publications_from_account()

        # Verify duration dates converted to datetime
        call_args = mock_create.call_args[0][0]
        assert "duration_start" in call_args
        assert "duration_end" in call_args
        assert isinstance(call_args["duration_start"], datetime)
        assert isinstance(call_args["duration_end"], datetime)
        assert call_args["duration_start"].date() == date(2024, 1, 1)
        assert call_args["duration_end"].date() == date(2024, 12, 31)


@pytest.mark.asyncio
async def test_sync_updates_publication_with_new_duration_dates(
    discovery_service: PublicationDiscoveryService,
    mock_httpx_client: AsyncMock,
    existing_publication: dict,
) -> None:
    """Test that duration dates get updated when subscription renews."""
    # Setup: New subscription with extended duration
    new_subscription = Subscription(
        name="Megatrend Folger",
        subscription_id="megatrend-folger",
        subscription_number="123456",
        content_url="https://example.com/megatrend",
        subscription_type="Megatrend Folger",
        duration="01.01.2025 - 31.12.2025",
        duration_start=date(2025, 1, 1),
        duration_end=date(2025, 12, 31),
    )

    mock_httpx_client.discover_subscriptions.return_value = [new_subscription]

    with (
        patch(
            "depotbutler.services.publication_discovery_service.get_publications",
            new_callable=AsyncMock,
        ) as mock_get_pubs,
        patch(
            "depotbutler.services.publication_discovery_service.update_publication",
            new_callable=AsyncMock,
        ) as mock_update,
    ):
        mock_get_pubs.return_value = [existing_publication]
        mock_update.return_value = True

        # Execute
        await discovery_service.sync_publications_from_account()

        # Verify duration dates updated
        pub_id, update_data = mock_update.call_args[0]
        assert "duration_start" in update_data
        assert "duration_end" in update_data
        assert update_data["duration_start"].date() == date(2025, 1, 1)
        assert update_data["duration_end"].date() == date(2025, 12, 31)


# ============================================================================
# Test: Matching Logic
# ============================================================================


@pytest.mark.asyncio
async def test_sync_matches_by_subscription_id(
    discovery_service: PublicationDiscoveryService,
    mock_httpx_client: AsyncMock,
    sample_subscriptions: list[Subscription],
) -> None:
    """Test that subscriptions match publications by subscription_id."""
    # Setup: Publication with different publication_id but same subscription_id
    existing = {
        "publication_id": "custom-id-123",  # Different from subscription_id
        "subscription_id": "megatrend-folger",  # Matches subscription
        "discovered": True,
    }

    mock_httpx_client.discover_subscriptions.return_value = [sample_subscriptions[0]]

    with (
        patch(
            "depotbutler.services.publication_discovery_service.get_publications",
            new_callable=AsyncMock,
        ) as mock_get_pubs,
        patch(
            "depotbutler.services.publication_discovery_service.update_publication",
            new_callable=AsyncMock,
        ) as mock_update,
    ):
        mock_get_pubs.return_value = [existing]
        mock_update.return_value = True

        # Execute
        result = await discovery_service.sync_publications_from_account()

        # Verify: Should update (not create new)
        assert result["updated_count"] == 1
        assert result["new_count"] == 0

        # Verify updated using publication_id (not subscription_id)
        pub_id, _ = mock_update.call_args[0]
        assert pub_id == "custom-id-123"


@pytest.mark.asyncio
async def test_sync_ignores_publications_without_subscription_id(
    discovery_service: PublicationDiscoveryService,
    mock_httpx_client: AsyncMock,
    sample_subscriptions: list[Subscription],
) -> None:
    """Test that publications without subscription_id are not matched."""
    # Setup: Publication without subscription_id
    pub_without_sub_id = {
        "publication_id": "manual-pub",
        "name": "Manually Created",
        # No subscription_id field
        "active": True,
    }

    mock_httpx_client.discover_subscriptions.return_value = [sample_subscriptions[0]]

    with (
        patch(
            "depotbutler.services.publication_discovery_service.get_publications",
            new_callable=AsyncMock,
        ) as mock_get_pubs,
        patch(
            "depotbutler.services.publication_discovery_service.create_publication",
            new_callable=AsyncMock,
        ) as mock_create,
    ):
        mock_get_pubs.return_value = [pub_without_sub_id]
        mock_create.return_value = True

        # Execute
        result = await discovery_service.sync_publications_from_account()

        # Verify: Should create new (not update manual publication)
        assert result["new_count"] == 1
        assert result["updated_count"] == 0
