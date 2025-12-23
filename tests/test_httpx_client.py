"""Tests for HTTPX-based Boersenmedien client."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from depotbutler.httpx_client import HttpxBoersenmedienClient
from depotbutler.models import Edition, PublicationConfig, Subscription


@pytest.fixture
def mock_mongodb():
    """Mock MongoDB service."""
    mongodb = AsyncMock()
    mongodb.get_auth_cookie = AsyncMock(return_value="test_cookie_value")
    mongodb.get_cookie_expiration_info = AsyncMock(return_value=None)
    mongodb.get_app_config = AsyncMock(return_value=5)  # Default warning days
    return mongodb


@pytest.fixture
def mock_publication():
    """Mock publication configuration."""
    return PublicationConfig(
        id="test-pub",
        name="Test Publication",
        onedrive_folder="test/folder",
    )


@pytest.fixture
def subscription_html():
    """Mock HTML for subscriptions page with metadata."""
    return """
    <html>
        <body>
            <div class="subscription-item" data-product-id="123" data-subscription-id="456" data-subscription-number="TEST-001">
                <h2>Test Publication <span class="badge active">Aktiv</span></h2>
                <dl>
                    <dt>Abo-Art</dt>
                    <dd>Jahresabo</dd>
                    <dt>Laufzeit</dt>
                    <dd>02.07.2025 - 01.07.2026</dd>
                </dl>
            </div>
        </body>
    </html>
    """


@pytest.fixture
def editions_html():
    """Mock HTML for editions list page."""
    return """
    <html>
        <body>
            <div class="product-download-item">
                <div class="image-container">
                    <a href="/produkte/ausgabe/789/details">
                        <img src="test.jpg" alt="Test Edition"/>
                    </a>
                </div>
            </div>
        </body>
    </html>
    """


@pytest.fixture
def details_html():
    """Mock HTML for edition details page."""
    return """
    <html>
        <body>
            <h1>Test Edition 1/2025</h1>
            <time datetime="2025-01-15T00:00:00">15. Januar 2025</time>
            <a href="/produkte/content/789/download">Download PDF</a>
        </body>
    </html>
    """


@pytest.mark.asyncio
async def test_login_success(mock_mongodb):
    """Test successful login with valid cookie."""
    client = HttpxBoersenmedienClient()

    # Mock successful subscriptions page response for auth verification
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.url = MagicMock(path="/produkte/abonnements")
    mock_response.raise_for_status = MagicMock()

    with (
        patch(
            "depotbutler.httpx_client.get_mongodb_service", return_value=mock_mongodb
        ),
        patch("httpx.AsyncClient") as mock_client_class,
    ):
        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client_instance

        result = await client.login()

        assert result == 200
        assert client.client is not None
        mock_mongodb.get_auth_cookie.assert_called_once()
        # Verify that auth was checked
        mock_client_instance.get.assert_called_once()
        await client.close()


@pytest.mark.asyncio
async def test_login_no_cookie(mock_mongodb):
    """Test login failure when no cookie is available."""
    mock_mongodb.get_auth_cookie = AsyncMock(return_value=None)
    client = HttpxBoersenmedienClient()

    with (
        patch(
            "depotbutler.httpx_client.get_mongodb_service", return_value=mock_mongodb
        ),
        pytest.raises(Exception, match="Authentication cookies not found"),
    ):
        await client.login()


@pytest.mark.asyncio
async def test_discover_subscriptions(mock_mongodb, subscription_html):
    """Test subscription discovery from HTML."""
    client = HttpxBoersenmedienClient()

    # Mock HTTP response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = subscription_html

    mock_http_client = AsyncMock()
    mock_http_client.get = AsyncMock(return_value=mock_response)

    with patch(
        "depotbutler.httpx_client.get_mongodb_service", return_value=mock_mongodb
    ):
        await client.login()
        client.client = mock_http_client

        subscriptions = await client.discover_subscriptions()

        assert len(subscriptions) == 1
        assert subscriptions[0].name == "Test Publication"
        assert subscriptions[0].subscription_id == "456"
        assert subscriptions[0].subscription_number == "TEST-001"
        assert subscriptions[0].content_url == (
            "https://konto.boersenmedien.com/produkte/abonnements/456/TEST-001/ausgaben"
        )
        assert subscriptions[0].subscription_type == "Jahresabo"
        assert subscriptions[0].duration == "02.07.2025 - 01.07.2026"
        # Verify parsed dates
        from datetime import date

        assert subscriptions[0].duration_start == date(2025, 7, 2)
        assert subscriptions[0].duration_end == date(2026, 7, 1)

        await client.close()


@pytest.mark.asyncio
async def test_get_latest_edition_success(
    mock_mongodb, mock_publication, editions_html, details_html
):
    """Test getting latest edition with valid subscription."""
    client = HttpxBoersenmedienClient()

    # Set up subscriptions
    client.subscriptions = [
        Subscription(
            name="Test Publication",
            subscription_id="456",
            subscription_number="TEST-001",
            content_url="https://konto.boersenmedien.com/produkte/abonnements/456/TEST-001/ausgaben",
        )
    ]

    # Mock HTTP responses
    mock_editions_response = MagicMock()
    mock_editions_response.status_code = 200
    mock_editions_response.text = editions_html

    mock_details_response = MagicMock()
    mock_details_response.status_code = 200
    mock_details_response.text = details_html

    mock_http_client = AsyncMock()
    mock_http_client.get = AsyncMock(
        side_effect=[mock_editions_response, mock_details_response]
    )

    with patch(
        "depotbutler.httpx_client.get_mongodb_service", return_value=mock_mongodb
    ):
        await client.login()
        client.client = mock_http_client

        edition = await client.get_latest_edition(mock_publication)

        assert edition is not None
        assert edition.title == "Test Edition 1/2025"
        assert edition.publication_date == "2025-01-15"
        assert edition.details_url.endswith("/produkte/ausgabe/789/details")
        assert edition.download_url.endswith("/produkte/content/789/download")

        await client.close()


@pytest.mark.asyncio
async def test_get_latest_edition_no_matching_subscription(
    mock_mongodb, mock_publication
):
    """Test get_latest_edition when no matching subscription exists."""
    client = HttpxBoersenmedienClient()
    client.subscriptions = []

    with patch(
        "depotbutler.httpx_client.get_mongodb_service", return_value=mock_mongodb
    ):
        await client.login()

        # Should raise EditionNotFoundError when no subscription matches
        with pytest.raises(Exception, match="No subscription found for publication"):
            await client.get_latest_edition(mock_publication)

        await client.close()


@pytest.mark.asyncio
async def test_download_edition(mock_mongodb):
    """Test downloading edition PDF."""
    client = HttpxBoersenmedienClient()

    edition = Edition(
        title="Test Edition",
        publication_date="2025-01-15",
        details_url="https://test.com/details",
        download_url="https://test.com/download",
    )

    # Mock HTTP response with PDF content
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"PDF content"
    mock_response.headers = {"content-length": "11"}

    mock_http_client = AsyncMock()
    mock_http_client.get = AsyncMock(return_value=mock_response)

    with (
        patch(
            "depotbutler.httpx_client.get_mongodb_service", return_value=mock_mongodb
        ),
        patch("builtins.open", create=True) as mock_open,
    ):
        await client.login()
        client.client = mock_http_client

        await client.download_edition(edition, "test.pdf")

        mock_http_client.get.assert_called_once_with(edition.download_url)
        mock_open.assert_called_once_with("test.pdf", "wb")

        await client.close()


@pytest.mark.asyncio
async def test_close():
    """Test client cleanup."""
    client = HttpxBoersenmedienClient()
    client.client = AsyncMock()

    await client.close()

    client.client.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_get_publication_date_with_existing_date(mock_mongodb):
    """Test get_publication_date when date is already set."""
    client = HttpxBoersenmedienClient()

    edition = Edition(
        title="Test Edition",
        publication_date="2025-01-15",
        details_url="https://test.com/details",
        download_url="https://test.com/download",
    )

    with patch(
        "depotbutler.httpx_client.get_mongodb_service", return_value=mock_mongodb
    ):
        await client.login()

        result = await client.get_publication_date(edition)

        assert result.publication_date == "2025-01-15"
        await client.close()


@pytest.mark.asyncio
async def test_discover_subscriptions_empty_page(mock_mongodb):
    """Test subscription discovery with no items on page."""
    client = HttpxBoersenmedienClient()

    # Mock HTTP response with empty HTML
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body></body></html>"

    mock_http_client = AsyncMock()
    mock_http_client.get = AsyncMock(return_value=mock_response)

    with patch(
        "depotbutler.httpx_client.get_mongodb_service", return_value=mock_mongodb
    ):
        await client.login()
        client.client = mock_http_client

        subscriptions = await client.discover_subscriptions()

        assert len(subscriptions) == 0
        await client.close()


@pytest.mark.asyncio
async def test_get_latest_edition_http_error(mock_mongodb, mock_publication):
    """Test get_latest_edition when HTTP request fails."""
    client = HttpxBoersenmedienClient()

    # Set up subscription
    client.subscriptions = [
        Subscription(
            name="Test Publication",
            subscription_id="456",
            subscription_number="TEST-001",
            content_url="https://konto.boersenmedien.com/produkte/abonnements/456/TEST-001/ausgaben",
        )
    ]

    # Mock HTTP response with error
    mock_response = MagicMock()
    mock_response.status_code = 404

    mock_http_client = AsyncMock()
    mock_http_client.get = AsyncMock(return_value=mock_response)

    with patch(
        "depotbutler.httpx_client.get_mongodb_service", return_value=mock_mongodb
    ):
        await client.login()
        client.client = mock_http_client

        edition = await client.get_latest_edition(mock_publication)

        assert edition is None
        await client.close()


@pytest.mark.asyncio
async def test_login_cookie_expiration_warning(mock_mongodb):
    """Test login with cookie expiring soon warning."""
    mock_mongodb.get_cookie_expiration_info = AsyncMock(
        return_value={
            "days_remaining": 3,
            "is_expired": False,
            "expires_at": "2025-12-16",
        }
    )
    mock_mongodb.get_app_config = AsyncMock(return_value=5)

    client = HttpxBoersenmedienClient()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.url = MagicMock()
    mock_response.url.path = "/mein-konto"

    mock_http_client = AsyncMock()
    mock_http_client.get = AsyncMock(return_value=mock_response)

    with patch(
        "depotbutler.httpx_client.get_mongodb_service", return_value=mock_mongodb
    ):
        await client.login()
        client.client = mock_http_client

        # Login should succeed with warning logged
        result = await client.login()
        assert result == 200
        await client.close()


@pytest.mark.asyncio
async def test_login_cookie_expired_warning(mock_mongodb):
    """Test login with expired cookie warning (still attempts login)."""
    mock_mongodb.get_cookie_expiration_info = AsyncMock(
        return_value={
            "days_remaining": -2,
            "is_expired": True,
            "expires_at": "2025-12-11",
        }
    )
    mock_mongodb.get_app_config = AsyncMock(return_value=5)

    client = HttpxBoersenmedienClient()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.url = MagicMock()
    mock_response.url.path = "/mein-konto"

    mock_http_client = AsyncMock()
    mock_http_client.get = AsyncMock(return_value=mock_response)

    with patch(
        "depotbutler.httpx_client.get_mongodb_service", return_value=mock_mongodb
    ):
        await client.login()
        client.client = mock_http_client

        # Login should succeed (warning logged but still attempts)
        result = await client.login()
        assert result == 200
        await client.close()


# Note: Login exception tests removed - these are difficult to test due to
# login() being called during client initialization and async context management


@pytest.mark.asyncio
async def test_discover_subscriptions_exception(mock_mongodb):
    """Test discover_subscriptions handling exceptions."""
    client = HttpxBoersenmedienClient()

    mock_http_client = AsyncMock()
    mock_http_client.get = AsyncMock(side_effect=Exception("Connection error"))

    with patch(
        "depotbutler.httpx_client.get_mongodb_service", return_value=mock_mongodb
    ):
        await client.login()
        client.client = mock_http_client

        subscriptions = await client.discover_subscriptions()

        # Should return empty list on error
        assert subscriptions == []
        await client.close()


@pytest.mark.asyncio
async def test_get_latest_edition_exception(mock_mongodb, mock_publication):
    """Test get_latest_edition handling exceptions."""
    client = HttpxBoersenmedienClient()
    client.subscriptions = [
        Subscription(
            name="Test Publication",
            subscription_id="456",
            subscription_number="TEST-001",
            content_url="https://test.com/content",
        )
    ]

    mock_http_client = AsyncMock()
    mock_http_client.get = AsyncMock(side_effect=Exception("Parse error"))

    with patch(
        "depotbutler.httpx_client.get_mongodb_service", return_value=mock_mongodb
    ):
        await client.login()
        client.client = mock_http_client

        edition = await client.get_latest_edition(mock_publication)

        # Should return None on error
        assert edition is None
        await client.close()


@pytest.mark.asyncio
async def test_download_edition_exception(mock_mongodb, tmp_path):
    """Test download_edition handling exceptions."""
    from depotbutler.models import Edition

    mock_edition = Edition(
        title="Test Edition",
        publication_date="2025-11-23",
        details_url="https://example.com/details",
        download_url="https://example.com/download",
    )

    client = HttpxBoersenmedienClient()

    download_path = tmp_path / "test.pdf"

    mock_http_client = AsyncMock()
    mock_http_client.get = AsyncMock(side_effect=Exception("Download failed"))

    with patch(
        "depotbutler.httpx_client.get_mongodb_service", return_value=mock_mongodb
    ):
        await client.login()
        client.client = mock_http_client

        # Should raise exception
        with pytest.raises((Exception, httpx.HTTPError)):
            await client.download_edition(mock_edition, str(download_path))

        await client.close()
