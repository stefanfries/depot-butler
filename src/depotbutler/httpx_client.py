"""
HTTPX-based client for boersenmedien.com.
Uses cookie authentication - no browser automation needed.
"""

from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from depotbutler.db.mongodb import get_mongodb_service
from depotbutler.exceptions import (
    AuthenticationError,
    ConfigurationError,
    EditionNotFoundError,
    TransientError,
)
from depotbutler.models import Edition, Subscription
from depotbutler.publications import PublicationConfig
from depotbutler.settings import Settings
from depotbutler.utils.logger import get_logger

settings = Settings()
logger = get_logger(__name__)


class HttpxBoersenmedienClient:
    """HTTPX-based client for boersenmedien.com using cookie authentication."""

    def __init__(self) -> None:
        self.base_url = settings.boersenmedien.base_url
        self.client: httpx.AsyncClient | None = None
        self.subscriptions: list[Subscription] = []

    async def login(self) -> int:
        """
        Ensure authenticated session using cookie from MongoDB.
        """
        logger.info("Authenticating with boersenmedien.com...")

        try:
            # Get cookie from MongoDB
            mongodb = await get_mongodb_service()

            # Check cookie expiration (informational only - still attempt login)
            expiration_info = await mongodb.get_cookie_expiration_info()
            if expiration_info:
                expires_at = expiration_info.get("expires_at")
                days_remaining = expiration_info.get("days_remaining")
                is_expired = expiration_info.get("is_expired")

                # Get warning threshold from MongoDB config (default: 5 days)
                warning_days = await mongodb.get_app_config(
                    "cookie_warning_days", default=5
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

            cookie_value = await mongodb.get_auth_cookie()

            if not cookie_value:
                logger.error("=" * 70)
                logger.error("NO COOKIES FOUND!")
                logger.error("=" * 70)
                logger.error("You need to export cookies from your browser first.")
                logger.error("Run: uv run python scripts/update_cookie_mongodb.py")
                logger.error("")
                logger.error("Steps:")
                logger.error(
                    "1. Login to https://login.boersenmedien.com/ in your browser"
                )
                logger.error("2. Copy the .AspNetCore.Cookies value from DevTools")
                logger.error("3. Run the cookie update script")
                logger.error("=" * 70)
                raise ConfigurationError(
                    "Authentication cookies not found. "
                    "Run: uv run python scripts/update_cookie_mongodb.py"
                )

            logger.info(f"✓ Loaded cookie from MongoDB (length: {len(cookie_value)})")

            # Create HTTPX client with cookie
            cookies = {".AspNetCore.Cookies": cookie_value}

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
            }

            self.client = httpx.AsyncClient(
                cookies=cookies, headers=headers, follow_redirects=True, timeout=30.0
            )

            # Verify authentication by checking subscriptions page
            try:
                test_response = await self.client.get(
                    f"{self.base_url}/produkte/abonnements"
                )

                # Check for authentication failure
                if test_response.status_code in [401, 403]:
                    logger.error(
                        "❌ Authentication failed: Cookie is invalid or expired"
                    )
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
                logger.info("✓ Authenticated successfully")
                return 200  # Success

            except (AuthenticationError, ConfigurationError):
                # Re-raise domain exceptions as-is
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

        except (AuthenticationError, ConfigurationError, TransientError):
            # Re-raise domain exceptions
            raise
        except Exception as e:
            logger.error(f"Unexpected authentication error: {e}")
            raise TransientError(f"Authentication failed: {e}") from e

    async def discover_subscriptions(self) -> list[Subscription]:
        """
        Auto-discover all active subscriptions from account.
        """
        if not self.client:
            raise ConfigurationError("Must call login() first")

        subscriptions_url = f"{self.base_url}/produkte/abonnements"

        try:
            response = await self.client.get(subscriptions_url)

            if response.status_code != 200:
                logger.error(
                    f"Failed to access subscriptions page: {response.status_code}"
                )
                return []

            # Check if redirected to login
            if "login" in str(response.url).lower():
                logger.error("Session expired. Cookie no longer valid.")
                return []

            soup = BeautifulSoup(response.text, "html.parser")
            discovered = []
            subscription_items = soup.find_all("div", class_="subscription-item")

            logger.info(f"Found {len(subscription_items)} subscription items on page")

            for item in subscription_items:
                try:
                    subscription_number = str(item.get("data-subscription-number", ""))
                    subscription_id = str(item.get("data-subscription-id", ""))

                    if not subscription_number or not subscription_id:
                        logger.warning("Subscription item missing data attributes")
                        continue

                    # Extract subscription name from h2
                    name_elem = item.find("h2")
                    if not name_elem:
                        logger.warning(
                            f"No h2 found for subscription {subscription_id}"
                        )
                        continue

                    # Get text without the badge span
                    name = name_elem.get_text(strip=True)
                    # Remove "Aktiv" or "Inaktiv" badge text if present
                    name = name.replace("Aktiv", "").replace("Inaktiv", "").strip()

                    # Build the editions URL using subscription ID and number
                    # Pattern: /produkte/abonnements/{sub_id}/{sub_number}/ausgaben
                    content_url = f"{self.base_url}/produkte/abonnements/{subscription_id}/{subscription_number}/ausgaben"

                    # Parse subscription metadata (Laufzeit, Abo-Art) from dl/dt/dd structure
                    subscription_type = None
                    duration = None
                    duration_start = None
                    duration_end = None

                    # Look for dl elements containing subscription metadata
                    dl_elements = item.find_all("dl")
                    for dl in dl_elements:
                        dt_elements = dl.find_all("dt")
                        dd_elements = dl.find_all("dd")

                        for dt, dd in zip(dt_elements, dd_elements, strict=False):
                            label = dt.get_text(strip=True)
                            value = dd.get_text(strip=True)

                            if "Abo-Art" in label:
                                subscription_type = value
                            elif "Laufzeit" in label:
                                duration = value
                                # Parse German date format: "DD.MM.YYYY - DD.MM.YYYY"
                                if " - " in value:
                                    try:
                                        start_str, end_str = value.split(" - ")
                                        from datetime import datetime

                                        duration_start = datetime.strptime(
                                            start_str.strip(), "%d.%m.%Y"
                                        ).date()
                                        duration_end = datetime.strptime(
                                            end_str.strip(), "%d.%m.%Y"
                                        ).date()
                                    except ValueError as e:
                                        logger.warning(
                                            f"Failed to parse duration '{value}': {e}"
                                        )

                    subscription = Subscription(
                        subscription_number=subscription_number,
                        subscription_id=subscription_id,
                        name=name,
                        content_url=content_url,
                        subscription_type=subscription_type,
                        duration=duration,
                        duration_start=duration_start,
                        duration_end=duration_end,
                    )

                    discovered.append(subscription)
                    logger.info(
                        f"✓ Found subscription: {name} (ID: {subscription_id}, "
                        f"Type: {subscription_type}, Duration: {duration})"
                    )

                except Exception as e:
                    logger.warning(f"Error parsing subscription item: {e}")
                    continue

            self.subscriptions = discovered
            logger.info(f"✓ Discovered {len(discovered)} total subscriptions")
            return discovered

        except Exception as e:
            logger.error(f"Failed to discover subscriptions: {e}")
            return []

    async def get_latest_edition(
        self, publication: PublicationConfig
    ) -> Edition | None:
        """Get the latest edition for a publication."""
        if not self.client:
            raise ConfigurationError("Must call login() first")

        # Find the matching subscription for this publication
        subscription = None
        for sub in self.subscriptions:
            if (
                publication.name.lower() in sub.name.lower()
                or sub.name.lower() in publication.name.lower()
            ):
                subscription = sub
                break

        if not subscription:
            logger.error(
                f"No subscription found matching publication: {publication.name}"
            )
            logger.info(
                f"Available subscriptions: {[s.name for s in self.subscriptions]}"
            )
            raise EditionNotFoundError(
                f"No subscription found for publication: {publication.name}"
            )

        try:
            response = await self.client.get(subscription.content_url)

            if response.status_code != 200:
                logger.error(f"Failed to access editions page: {response.status_code}")
                return None

            soup = BeautifulSoup(response.text, "html.parser")

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

            # Fetch the details page to get title, download link, and publication date
            details_response = await self.client.get(details_url)

            if details_response.status_code != 200:
                logger.error(
                    f"Failed to access details page: {details_response.status_code}"
                )
                return None

            details_soup = BeautifulSoup(details_response.text, "html.parser")

            # Extract title from h1 element on details page
            title = ""
            h1_elem = details_soup.find("h1")
            if h1_elem:
                title = h1_elem.get_text(strip=True)

            if not title:
                logger.warning(
                    "Could not extract title from h1, using details URL as fallback"
                )
                title = details_url.split("/")[-2]  # Use edition ID as title

            logger.info(f"Found latest edition: {title}")

            # Find download link - look for /produkte/content/{id}/download pattern
            download_link = details_soup.find(
                "a", href=lambda x: x and "/download" in x
            )

            if not download_link:
                logger.error("No download link found on details page")
                # Save HTML for debugging
                logger.error(f"Details page URL was: {details_url}")
                return None

            download_url = str(download_link["href"])
            if not download_url.startswith("http"):
                download_url = self.base_url + download_url

            # Extract publication date from time element or other date indicator
            publication_date = ""
            time_elem = details_soup.find("time")
            if time_elem and time_elem.get("datetime"):
                datetime_value = str(time_elem["datetime"])
                publication_date = datetime_value.split("T")[0]
                logger.info(f"Extracted publication date: {publication_date}")
            else:
                logger.warning(
                    "No time element found, will try alternative date extraction"
                )

            edition = Edition(
                title=title,
                details_url=details_url,
                download_url=download_url,
                publication_date=publication_date,
            )

            logger.info(f"✓ Edition ready: {title}")
            return edition

        except Exception as e:
            logger.error(f"Failed to get latest edition: {e}", exc_info=True)
            return None

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
