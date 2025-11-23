"""Tests for BoersenmedienClient (client.py)."""

from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import httpx
import pytest

from depotbutler.client import BoersenmedienClient
from depotbutler.models import Edition, Subscription
from depotbutler.publications import PublicationConfig


@pytest.fixture
def mock_settings():
    """Create mock settings for client."""
    settings = MagicMock()
    settings.boersenmedien.base_url = "https://example.com"
    settings.boersenmedien.login_url = "https://example.com/login"
    settings.boersenmedien.username = MagicMock()
    settings.boersenmedien.username.get_secret_value.return_value = "test_user"
    settings.boersenmedien.password = MagicMock()
    settings.boersenmedien.password.get_secret_value.return_value = "test_pass"
    return settings


@pytest.fixture
def client(mock_settings):
    """Create BoersenmedienClient with mocked dependencies."""
    with patch("depotbutler.client.Settings", return_value=mock_settings):
        with patch("depotbutler.client.settings", mock_settings):
            return BoersenmedienClient()


@pytest.fixture
def mock_subscription():
    """Create a mock Subscription for testing."""
    return Subscription(
        name="Test Publication",
        subscription_number="12345",
        subscription_id="sub123",
        content_url="https://example.com/produkte/abonnements/sub123/12345/ausgaben",
    )


@pytest.fixture
def mock_publication_config():
    """Create a mock PublicationConfig for testing."""
    return PublicationConfig(
        id="test_pub",
        name="Test Publication",
        onedrive_folder="Test",
        subscription_number="12345",
        subscription_id="sub123",
    )


@pytest.fixture
def mock_edition():
    """Create a mock Edition for testing."""
    return Edition(
        title="Test Edition 47/2025",
        publication_date="2025-11-23",
        details_url="https://example.com/details",
        download_url="https://example.com/download",
    )


def test_client_initialization(client, mock_settings):
    """Test BoersenmedienClient initialization."""
    assert client.base_url == mock_settings.boersenmedien.base_url
    assert client.login_url == mock_settings.boersenmedien.login_url
    assert client.username.get_secret_value() == "test_user"
    assert client.password.get_secret_value() == "test_pass"
    assert isinstance(client.client, httpx.AsyncClient)
    assert client.subscriptions == []


@pytest.mark.asyncio
async def test_login_success(client):
    """Test successful login flow."""
    # Mock login page response with token
    mock_login_page = """
    <html>
        <form>
            <input name="__RequestVerificationToken" value="test_token_123" />
        </form>
    </html>
    """

    # Mock successful login response
    mock_login_response = """
    <html>
        <body>
            <a href="/logout">Abmelden</a>
        </body>
    </html>
    """

    mock_get_response = AsyncMock()
    mock_get_response.text = mock_login_page
    mock_get_response.raise_for_status = MagicMock()

    mock_post_response = AsyncMock()
    mock_post_response.text = mock_login_response
    mock_post_response.status_code = 200
    mock_post_response.raise_for_status = MagicMock()

    with patch.object(client.client, "get", return_value=mock_get_response):
        with patch.object(client.client, "post", return_value=mock_post_response):
            status = await client.login()

            assert status == 200
            # Verify post was called with correct payload
            client.client.post.assert_called_once()
            call_args = client.client.post.call_args
            payload = call_args[1]["data"]
            assert payload["__RequestVerificationToken"] == "test_token_123"
            assert payload["Username"] == "test_user"
            assert payload["Password"] == "test_pass"


@pytest.mark.asyncio
async def test_login_missing_token(client):
    """Test login when token is missing from page."""
    mock_login_page = "<html><form></form></html>"

    mock_get_response = AsyncMock()
    mock_get_response.text = mock_login_page
    mock_get_response.raise_for_status = MagicMock()

    with patch.object(client.client, "get", return_value=mock_get_response):
        with pytest.raises(
            ValueError, match="Could not find __RequestVerificationToken"
        ):
            await client.login()


@pytest.mark.asyncio
async def test_login_http_error(client):
    """Test login when HTTP error occurs."""
    mock_get_response = MagicMock()
    mock_get_response.text = "<html></html>"
    mock_get_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Error", request=MagicMock(), response=MagicMock()
    )

    with patch.object(client.client, "get", return_value=mock_get_response):
        with pytest.raises(httpx.HTTPStatusError):
            await client.login()


@pytest.mark.asyncio
async def test_discover_subscriptions_success(client):
    """Test successful subscription discovery."""
    mock_html = """
    <html>
        <div class="subscription-item" data-subscription-number="12345" data-subscription-id="sub123">
            <h2>Test Publication <span class="badge">Aktiv</span></h2>
        </div>
        <div class="subscription-item" data-subscription-number="67890" data-subscription-id="sub456">
            <h2>Another Publication <span class="badge">Inaktiv</span></h2>
        </div>
    </html>
    """

    mock_response = AsyncMock()
    mock_response.text = mock_html
    mock_response.raise_for_status = MagicMock()

    with patch.object(client.client, "get", return_value=mock_response):
        subscriptions = await client.discover_subscriptions()

        assert len(subscriptions) == 2
        assert subscriptions[0].name == "Test Publication"
        assert subscriptions[0].subscription_number == "12345"
        assert subscriptions[0].subscription_id == "sub123"
        assert subscriptions[1].name == "Another Publication"
        assert subscriptions[1].subscription_number == "67890"
        assert client.subscriptions == subscriptions


@pytest.mark.asyncio
async def test_discover_subscriptions_empty(client):
    """Test subscription discovery when no subscriptions found."""
    mock_html = "<html><body>No subscriptions</body></html>"

    mock_response = AsyncMock()
    mock_response.text = mock_html
    mock_response.raise_for_status = MagicMock()

    with patch.object(client.client, "get", return_value=mock_response):
        subscriptions = await client.discover_subscriptions()

        assert subscriptions == []
        assert client.subscriptions == []


@pytest.mark.asyncio
async def test_discover_subscriptions_http_error(client):
    """Test subscription discovery when HTTP error occurs."""
    mock_response = MagicMock()
    mock_response.text = "<html></html>"
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Error", request=MagicMock(), response=MagicMock()
    )

    with patch.object(client.client, "get", return_value=mock_response):
        subscriptions = await client.discover_subscriptions()

        # Should return empty list on error
        assert subscriptions == []


@pytest.mark.asyncio
async def test_discover_subscriptions_malformed_item(client):
    """Test subscription discovery with malformed items."""
    mock_html = """
    <html>
        <div class="subscription-item">
            <!-- Missing data attributes -->
            <h2>Test Publication</h2>
        </div>
        <div class="subscription-item" data-subscription-number="12345" data-subscription-id="sub123">
            <!-- Valid item -->
            <h2>Valid Publication</h2>
        </div>
    </html>
    """

    mock_response = AsyncMock()
    mock_response.text = mock_html
    mock_response.raise_for_status = MagicMock()

    with patch.object(client.client, "get", return_value=mock_response):
        subscriptions = await client.discover_subscriptions()

        # Should only get the valid subscription
        assert len(subscriptions) == 1
        assert subscriptions[0].name == "Valid Publication"


def test_get_subscription_by_number(client, mock_publication_config):
    """Test getting subscription by subscription_number."""
    client.subscriptions = [
        Subscription(
            name="Test Pub",
            subscription_number="12345",
            subscription_id="sub123",
            content_url="https://example.com/test",
        )
    ]

    subscription = client.get_subscription(mock_publication_config)

    assert subscription is not None
    assert subscription.subscription_number == "12345"


def test_get_subscription_by_name(client):
    """Test getting subscription by name match."""
    client.subscriptions = [
        Subscription(
            name="Test Publication Full Name",
            subscription_number="12345",
            subscription_id="sub123",
            content_url="https://example.com/test",
        )
    ]

    config = PublicationConfig(
        id="test",
        name="Test Publication",
        onedrive_folder="Test",
        subscription_number=None,  # No number, will match by name
        subscription_id=None,
    )

    subscription = client.get_subscription(config)

    assert subscription is not None
    assert subscription.subscription_number == "12345"


def test_get_subscription_not_found(client, mock_publication_config):
    """Test getting subscription when not found."""
    client.subscriptions = []

    subscription = client.get_subscription(mock_publication_config)

    assert subscription is None


def test_get_subscription_no_discovered(client, mock_publication_config):
    """Test getting subscription when none discovered."""
    subscription = client.get_subscription(mock_publication_config)

    assert subscription is None


@pytest.mark.asyncio
async def test_get_latest_edition_with_subscription(
    client, mock_subscription, mock_settings
):
    """Test getting latest edition with Subscription object."""
    mock_html = """
    <html>
        <article class="list-item universal-list-item">
            <h2><a>Test Edition 47/2025</a></h2>
            <header><a href="/details">Details</a></header>
            <footer><a href="/download">Download</a></footer>
        </article>
    </html>
    """

    mock_response = AsyncMock()
    mock_response.text = mock_html
    mock_response.raise_for_status = MagicMock()

    with patch.object(client.client, "get", return_value=mock_response):
        edition = await client.get_latest_edition(mock_subscription)

        assert edition.title == "Test Edition 47/2025"
        assert edition.details_url == f"{mock_settings.boersenmedien.base_url}/details"
        assert (
            edition.download_url == f"{mock_settings.boersenmedien.base_url}/download"
        )


@pytest.mark.asyncio
async def test_get_latest_edition_with_publication_config(
    client, mock_publication_config
):
    """Test getting latest edition with PublicationConfig."""
    mock_html = """
    <html>
        <article class="list-item universal-list-item">
            <h2><a>Test Edition</a></h2>
            <header><a href="/details">Details</a></header>
            <footer><a href="/download">Download</a></footer>
        </article>
    </html>
    """

    mock_response = AsyncMock()
    mock_response.text = mock_html
    mock_response.raise_for_status = MagicMock()

    with patch.object(client.client, "get", return_value=mock_response):
        edition = await client.get_latest_edition(mock_publication_config)

        assert edition.title == "Test Edition"


@pytest.mark.asyncio
async def test_get_latest_edition_not_found(client, mock_subscription):
    """Test getting latest edition when no article found."""
    mock_html = "<html><body>No articles</body></html>"

    mock_response = AsyncMock()
    mock_response.text = mock_html
    mock_response.raise_for_status = MagicMock()

    with patch.object(client.client, "get", return_value=mock_response):
        with pytest.raises(ValueError, match="No edition found"):
            await client.get_latest_edition(mock_subscription)


@pytest.mark.asyncio
async def test_get_latest_edition_with_undiscovered_publication(client):
    """Test getting latest edition with PublicationConfig that needs discovery."""
    config = PublicationConfig(
        id="test",
        name="Unknown Publication",
        onedrive_folder="Test",
        subscription_number=None,  # No hardcoded info
        subscription_id=None,
    )

    with pytest.raises(ValueError, match="Could not find subscription"):
        await client.get_latest_edition(config)


@pytest.mark.asyncio
async def test_get_publication_date(client, mock_edition):
    """Test getting publication date from edition details."""
    mock_html = """
    <html>
        <time datetime="2025-11-23T10:00:00">Nov 23, 2025</time>
    </html>
    """

    mock_response = AsyncMock()
    mock_response.text = mock_html
    mock_response.raise_for_status = MagicMock()

    with patch.object(client.client, "get", return_value=mock_response):
        updated_edition = await client.get_publication_date(mock_edition)

        assert updated_edition.publication_date == "2025-11-23T10:00:00"


@pytest.mark.asyncio
async def test_get_publication_date_not_found(client, mock_edition):
    """Test getting publication date when time element not found."""
    mock_html = "<html><body>No time element</body></html>"

    mock_response = AsyncMock()
    mock_response.text = mock_html
    mock_response.raise_for_status = MagicMock()

    with patch.object(client.client, "get", return_value=mock_response):
        updated_edition = await client.get_publication_date(mock_edition)

        assert updated_edition.publication_date == "unknown"


@pytest.mark.asyncio
async def test_download_edition(client, mock_edition, tmp_path):
    """Test downloading edition PDF."""
    dest_path = tmp_path / "test.pdf"
    pdf_content = b"PDF content here"

    mock_response = AsyncMock()
    mock_response.content = pdf_content
    mock_response.raise_for_status = MagicMock()

    with patch.object(client.client, "get", return_value=mock_response):
        response = await client.download_edition(mock_edition, str(dest_path))

        assert response == mock_response
        assert dest_path.exists()
        assert dest_path.read_bytes() == pdf_content


@pytest.mark.asyncio
async def test_download_edition_http_error(client, mock_edition, tmp_path):
    """Test download when HTTP error occurs."""
    dest_path = tmp_path / "test.pdf"

    mock_response = MagicMock()
    mock_response.content = b"test content"
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Error", request=MagicMock(), response=MagicMock()
    )

    with patch.object(client.client, "get", return_value=mock_response):
        with pytest.raises(httpx.HTTPStatusError):
            await client.download_edition(mock_edition, str(dest_path))


@pytest.mark.asyncio
async def test_close(client):
    """Test closing HTTP client."""
    mock_close = AsyncMock()
    client.client.aclose = mock_close

    await client.close()

    mock_close.assert_called_once()


@pytest.mark.asyncio
async def test_get_latest_edition_missing_elements(client, mock_subscription):
    """Test getting latest edition with missing optional elements."""
    mock_html = """
    <html>
        <article class="list-item universal-list-item">
            <!-- Missing h2, header, footer -->
        </article>
    </html>
    """

    mock_response = AsyncMock()
    mock_response.text = mock_html
    mock_response.raise_for_status = MagicMock()

    with patch.object(client.client, "get", return_value=mock_response):
        edition = await client.get_latest_edition(mock_subscription)

        assert edition.title == "Unknown"
        assert edition.details_url == ""
        assert edition.download_url == ""
