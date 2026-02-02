"""
HTTPX-based client for boersenmedien.com.
Uses cookie authentication - no browser automation needed.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

import httpx
from bs4 import BeautifulSoup

from depotbutler.db.mongodb import get_mongodb_service
from depotbutler.exceptions import (
    AuthenticationError,
    ConfigurationError,
    EditionNotFoundError,
    TransientError,
)
from depotbutler.models import Edition, PublicationConfig, Subscription
from depotbutler.settings import Settings
from depotbutler.utils.logger import get_logger

if TYPE_CHECKING:
    from bs4 import Tag

    from depotbutler.db.mongodb import MongoDBService

settings = Settings()
logger = get_logger(__name__)


class HttpxBoersenmedienClient:
    """HTTPX-based client for boersenmedien.com using cookie authentication."""

    def __init__(self) -> None:
        self.settings = settings  # Reference to module-level settings
        self.base_url = settings.boersenmedien.base_url
        self.client: httpx.AsyncClient | None = None
        self.subscriptions: list[Subscription] = []

    async def login(self) -> int:
        """
        Ensure authenticated session using cookie from MongoDB.
        """
        logger.info("Authenticating with boersenmedien.com...")

        try:
            # Get and validate cookie from MongoDB
            mongodb = await get_mongodb_service()
            await self._log_cookie_expiration_status(mongodb)
            cookie_value = await self._get_cookie_from_mongodb(mongodb)

            # Create authenticated client
            self.client = self._create_authenticated_client(cookie_value)

            # Verify authentication
            await self._verify_authentication()

            logger.info("✓ Authenticated successfully")
            return 200

        except (AuthenticationError, ConfigurationError, TransientError):
            raise
        except Exception as e:
            logger.error(f"Unexpected authentication error: {e}")
            raise TransientError(f"Authentication failed: {e}") from e

    async def _log_cookie_expiration_status(self, mongodb: MongoDBService) -> None:
        """Log cookie expiration information."""
        expiration_info = await mongodb.get_cookie_expiration_info()
        if not expiration_info:
            return

        expires_at = expiration_info.get("expires_at")
        days_remaining = expiration_info.get("days_remaining")
        is_expired = expiration_info.get("is_expired")

        warning_days = await mongodb.get_app_config(
            "cookie_warning_days",
            default=self.settings.notifications.cookie_warning_days,
        )

        if is_expired:
            logger.warning("⚠️  Cookie estimated to be expired!")
            logger.warning(f"   Estimated expiration: {expires_at}")
            logger.warning("   This is an estimate. Attempting login anyway...")
        elif days_remaining is not None and days_remaining <= warning_days:
            logger.warning("⚠️  Cookie will expire soon!")
            logger.warning(f"   Expires on: {expires_at}")
            logger.warning(f"   Days remaining: {days_remaining}")
        elif expires_at:
            logger.info(
                f"Cookie expires on {expires_at} ({days_remaining} days remaining)"
            )

    async def _get_cookie_from_mongodb(self, mongodb: MongoDBService) -> str:
        """
        Retrieve authentication cookie from MongoDB.

        Args:
            mongodb: MongoDB service instance

        Returns:
            Cookie value

        Raises:
            ConfigurationError: If cookie not found
        """
        cookie_value = await mongodb.get_auth_cookie()

        if not cookie_value:
            logger.error("=" * 70)
            logger.error("NO COOKIES FOUND!")
            logger.error("=" * 70)
            logger.error("You need to export cookies from your browser first.")
            logger.error("Run: uv run python scripts/update_cookie_mongodb.py")
            logger.error("")
            logger.error("Steps:")
            logger.error("1. Login to https://login.boersenmedien.com/ in your browser")
            logger.error("2. Copy the .AspNetCore.Cookies value from DevTools")
            logger.error("3. Run the cookie update script")
            logger.error("=" * 70)
            raise ConfigurationError(
                "Authentication cookies not found. "
                "Run: uv run python scripts/update_cookie_mongodb.py"
            )

        logger.info(f"✓ Loaded cookie from MongoDB (length: {len(cookie_value)})")
        return cookie_value

    def _create_authenticated_client(self, cookie_value: str) -> httpx.AsyncClient:
        """Create HTTPX client with authentication cookie."""
        cookies = {".AspNetCore.Cookies": cookie_value}

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        }

        return httpx.AsyncClient(
            cookies=cookies,
            headers=headers,
            follow_redirects=True,
            timeout=self.settings.http.request_timeout,
        )

    async def _verify_authentication(self) -> None:
        """
        Verify authentication by checking subscriptions page.

        Raises:
            AuthenticationError: If authentication fails
            TransientError: For network or server errors
        """
        if not self.client:
            raise ConfigurationError("Client not initialized")

        try:
            test_response = await self.client.get(
                f"{self.base_url}/produkte/abonnements"
            )

            # Check for authentication failure
            if test_response.status_code in [401, 403]:
                logger.error("❌ Authentication failed: Cookie is invalid or expired")
                logger.error(f"   HTTP Status: {test_response.status_code}")
                logger.error(
                    "   Please update the cookie using: uv run python scripts/update_cookie_mongodb.py"
                )
                raise AuthenticationError(
                    f"Cookie is invalid or expired (HTTP {test_response.status_code}). "
                    f"Please update using: uv run python scripts/update_cookie_mongodb.py"
                )

            # Check if redirected to login page
            if "login" in test_response.url.path.lower():
                logger.error("❌ Authentication failed: Redirected to login page")
                logger.error(
                    "   Please update the cookie using: uv run python scripts/update_cookie_mongodb.py"
                )
                raise AuthenticationError(
                    "Cookie is invalid or expired (redirected to login). "
                    "Please update using: uv run python scripts/update_cookie_mongodb.py"
                )

            test_response.raise_for_status()

        except (AuthenticationError, ConfigurationError):
            raise
        except httpx.TimeoutException as e:
            logger.error(f"Authentication timeout: {e}")
            raise TransientError("Authentication timeout - please try again") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500:
                raise TransientError(
                    f"Server error during authentication: {e.response.status_code}"
                ) from e
            raise AuthenticationError(
                f"Authentication failed with HTTP {e.response.status_code}"
            ) from e
        except Exception as e:
            logger.error(f"Failed to verify authentication: {e}")
            raise TransientError(f"Authentication verification failed: {e}") from e

    async def discover_subscriptions(self) -> list[Subscription]:
        """
        Auto-discover all active subscriptions from account.
        """
        if not self.client:
            raise ConfigurationError("Must call login() first")

        try:
            html = await self._fetch_subscriptions_page()
            if not html:
                return []

            subscription_items = self._parse_subscription_items(html)
            logger.info(f"Found {len(subscription_items)} subscription items on page")

            discovered = []
            for item in subscription_items:
                try:
                    subscription = self._extract_subscription_data(item)
                    if subscription:
                        discovered.append(subscription)
                        logger.info(
                            f"✓ Found subscription: {subscription.name} "
                            f"(ID: {subscription.subscription_id}, "
                            f"Type: {subscription.subscription_type}, "
                            f"Duration: {subscription.duration})"
                        )
                except Exception as e:
                    logger.warning(f"Error parsing subscription item: {e}")
                    continue

            self.subscriptions = discovered
            logger.info(f"✓ Discovered {len(discovered)} total subscriptions")
            return discovered

        except AuthenticationError:
            # Propagate authentication errors to workflow level
            raise
        except Exception as e:
            logger.error(f"Failed to discover subscriptions: {e}")
            return []

    async def _fetch_subscriptions_page(self) -> str | None:
        """Fetch subscriptions page HTML."""
        if not self.client:
            return None

        subscriptions_url = f"{self.base_url}/produkte/abonnements"
        response = await self.client.get(subscriptions_url)

        if response.status_code != 200:
            logger.error(f"Failed to access subscriptions page: {response.status_code}")
            raise AuthenticationError(
                f"Failed to access subscriptions page: HTTP {response.status_code}"
            )

        if "login" in str(response.url).lower():
            logger.error("Session expired. Cookie no longer valid.")
            raise AuthenticationError(
                "Session expired - cookie is invalid or expired. "
                "Please update authentication cookie using update_cookie_mongodb.py script."
            )

        return str(response.text)

    def _parse_subscription_items(self, html: str) -> list[Tag]:
        """Parse subscription items from HTML."""
        soup = BeautifulSoup(html, "html.parser")
        items = soup.find_all("div", class_="subscription-item")
        return list(items)

    def _extract_subscription_data(self, item: Tag) -> Subscription | None:
        """Extract subscription data from HTML element."""
        subscription_number = str(item.get("data-subscription-number", ""))
        subscription_id = str(item.get("data-subscription-id", ""))

        if not subscription_number or not subscription_id:
            logger.warning("Subscription item missing data attributes")
            return None

        name = self._extract_subscription_name(item, subscription_id)
        if not name:
            return None

        content_url = (
            f"{self.base_url}/produkte/abonnements/"
            f"{subscription_id}/{subscription_number}/ausgaben"
        )

        # Extract metadata
        metadata = self._extract_subscription_metadata(item)

        return Subscription(
            subscription_number=subscription_number,
            subscription_id=subscription_id,
            name=name,
            content_url=content_url,
            subscription_type=metadata.get("type"),
            duration=metadata.get("duration"),
            duration_start=metadata.get("duration_start"),
            duration_end=metadata.get("duration_end"),
        )

    def _extract_subscription_name(self, item: Tag, subscription_id: str) -> str | None:
        """Extract subscription name from HTML element."""
        name_elem = item.find("h2")
        if not name_elem:
            logger.warning(f"No h2 found for subscription {subscription_id}")
            return None

        name_text = name_elem.get_text(strip=True)
        # Remove badge text
        cleaned_name = (
            str(name_text).replace("Aktiv", "").replace("Inaktiv", "").strip()
        )
        return cleaned_name

    def _extract_subscription_metadata(self, item: Tag) -> dict[str, Any]:
        """Extract subscription metadata (type, duration, dates)."""
        metadata: dict[str, Any] = {
            "type": None,
            "duration": None,
            "duration_start": None,
            "duration_end": None,
        }

        dl_elements = item.find_all("dl")
        for dl in dl_elements:
            dt_elements = dl.find_all("dt")
            dd_elements = dl.find_all("dd")

            for dt, dd in zip(dt_elements, dd_elements, strict=False):
                label = dt.get_text(strip=True)
                value = dd.get_text(strip=True)

                if "Abo-Art" in label:
                    metadata["type"] = value
                elif "Laufzeit" in label:
                    metadata["duration"] = value
                    # Parse dates if present
                    dates = self._parse_duration_dates(value)
                    if dates:
                        metadata["duration_start"], metadata["duration_end"] = dates

        return metadata

    def _parse_duration_dates(self, duration_str: str) -> tuple[date, date] | None:
        """Parse German date format from duration string."""
        if " - " not in duration_str:
            return None

        try:
            start_str, end_str = duration_str.split(" - ")
            duration_start = datetime.strptime(start_str.strip(), "%d.%m.%Y").date()
            duration_end = datetime.strptime(end_str.strip(), "%d.%m.%Y").date()
            return (duration_start, duration_end)
        except ValueError as e:
            logger.warning(f"Failed to parse duration '{duration_str}': {e}")
            return None

    async def get_latest_edition(
        self, publication: PublicationConfig
    ) -> Edition | None:
        """Get the latest edition for a publication."""
        if not self.client:
            raise ConfigurationError("Must call login() first")

        # Find matching subscription
        subscription = self._find_subscription(publication)

        try:
            # Get editions list page
            response = await self.client.get(subscription.content_url)
            if response.status_code != 200:
                logger.error(f"Failed to access editions page: {response.status_code}")
                return None

            # Extract latest edition details URL
            details_url = self._extract_details_url(response.text)
            if not details_url:
                return None

            # Fetch and parse edition details
            edition = await self._fetch_edition_details(details_url)
            if edition:
                logger.info(f"✓ Edition ready: {edition.title}")

            return edition

        except Exception as e:
            logger.error(f"Failed to get latest edition: {e}", exc_info=True)
            return None

    def _find_subscription(self, publication: PublicationConfig) -> Subscription:
        """
        Find subscription matching publication.

        Args:
            publication: Publication configuration

        Returns:
            Matching subscription

        Raises:
            EditionNotFoundError: If no matching subscription found
        """
        for sub in self.subscriptions:
            if (
                publication.name.lower() in sub.name.lower()
                or sub.name.lower() in publication.name.lower()
            ):
                return sub

        logger.error(f"No subscription found matching publication: {publication.name}")
        logger.info(f"Available subscriptions: {[s.name for s in self.subscriptions]}")
        raise EditionNotFoundError(
            f"No subscription found for publication: {publication.name} "
            f"(total subscriptions discovered: {len(self.subscriptions)})"
        )

    def _extract_details_url(self, html: str) -> str | None:
        """
        Extract latest edition details URL from HTML.

        Args:
            html: HTML content of editions list page

        Returns:
            Details URL or None if not found
        """
        soup = BeautifulSoup(html, "html.parser")

        # Find all edition links (they go to /ausgabe/{edition_id}/details)
        edition_links = soup.find_all(
            "a", href=lambda x: x and "/ausgabe/" in x and "/details" in x
        )

        if not edition_links:
            logger.warning("No edition links found on page")
            return None

        # Get the first edition link (latest)
        first_link = edition_links[0]
        details_url = str(first_link["href"])

        if not details_url.startswith("http"):
            details_url = self.base_url + details_url

        logger.info(f"Details URL: {details_url}")
        return details_url

    async def _fetch_edition_details(self, details_url: str) -> Edition | None:
        """
        Fetch and parse edition details from details page.

        Args:
            details_url: URL of edition details page

        Returns:
            Edition object or None if parsing failed
        """
        if not self.client:
            return None

        details_response = await self.client.get(details_url)
        if details_response.status_code != 200:
            logger.error(
                f"Failed to access details page: {details_response.status_code}"
            )
            return None

        details_soup = BeautifulSoup(details_response.text, "html.parser")

        # Extract title, download URL, and publication date
        title = self._extract_title(details_soup, details_url)
        download_url = self._extract_download_url(details_soup, details_url)
        publication_date = self._extract_publication_date(details_soup)

        if not download_url:
            logger.error("No download link found on details page")
            logger.error(f"Details page URL was: {details_url}")
            return None

        logger.info(f"Found latest edition: {title}")

        return Edition(
            title=title,
            details_url=details_url,
            download_url=download_url,
            publication_date=publication_date,
        )

    def _extract_title(self, soup: BeautifulSoup, details_url: str) -> str:
        """Extract title from details page."""
        h1_elem = soup.find("h1")
        if h1_elem:
            title_text = h1_elem.get_text(strip=True)
            return str(title_text)

        # Fallback: use edition ID from URL
        logger.warning("Could not extract title from h1, using details URL as fallback")
        return details_url.split("/")[-2]

    def _extract_download_url(
        self, soup: BeautifulSoup, details_url: str
    ) -> str | None:
        """Extract download URL from details page."""
        download_link = soup.find("a", href=lambda x: x and "/download" in x)
        if not download_link:
            return None

        download_url = str(download_link["href"])
        if not download_url.startswith("http"):
            download_url = self.base_url + download_url

        return download_url

    def _extract_publication_date(self, soup: BeautifulSoup) -> str:
        """Extract publication date from details page."""
        time_elem = soup.find("time")
        if time_elem and time_elem.get("datetime"):
            datetime_value = str(time_elem["datetime"])
            publication_date = datetime_value.split("T")[0]
            logger.info(f"Extracted publication date: {publication_date}")
            return publication_date

        logger.warning("No time element found, will try alternative date extraction")
        return ""

    async def get_publication_date(self, edition: Edition) -> Edition:
        """Extract publication date from edition details page."""
        if not self.client:
            raise Exception("Must call login() first")

        # If we already have a publication date, return it
        if edition.publication_date:
            return edition

        # If no details URL, use current date as fallback
        if not edition.details_url:
            edition.publication_date = datetime.now().strftime("%Y-%m-%d")
            logger.warning(
                f"No details URL available, using current date: {edition.publication_date}"
            )
            return edition

        try:
            response = await self.client.get(edition.details_url)

            if response.status_code != 200:
                logger.error(f"Failed to access details page: {response.status_code}")
                edition.publication_date = datetime.now().strftime("%Y-%m-%d")
                return edition

            soup = BeautifulSoup(response.text, "html.parser")

            # Look for time element with datetime attribute
            time_elem = soup.find("time")
            if time_elem and time_elem.get("datetime"):
                datetime_value = str(time_elem["datetime"])
                edition.publication_date = datetime_value.split("T")[0]
                logger.info(
                    f"Extracted publication date from details page: {edition.publication_date}"
                )
            else:
                # Fallback to current date
                edition.publication_date = datetime.now().strftime("%Y-%m-%d")
                logger.warning(
                    f"No date found on details page, using current date: {edition.publication_date}"
                )

            return edition

        except Exception as e:
            logger.error(f"Failed to get publication date: {e}")
            # Fallback to current date
            edition.publication_date = datetime.now().strftime("%Y-%m-%d")
            return edition

    async def download_edition(self, edition: Edition, filepath: str) -> None:
        """Download edition PDF to local file."""
        if not self.client:
            raise Exception("Must call login() first")

        try:
            logger.info(f"Downloading from: {edition.download_url}")

            response = await self.client.get(edition.download_url)

            if response.status_code != 200:
                raise Exception(f"Download failed with status {response.status_code}")

            # Write PDF to file
            with open(filepath, "wb") as f:
                f.write(response.content)

            logger.info(f"✓ Downloaded PDF to: {filepath}")

        except Exception as e:
            logger.error(f"Failed to download PDF: {e}")
            raise

    async def close(self) -> None:
        """Cleanup HTTP client resources."""
        if self.client:
            await self.client.aclose()
