"""
HTTPX-based client for boersenmedien.com.
Uses cookie authentication - no browser automation needed.
"""

from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from depotbutler.db.mongodb import get_mongodb_service
from depotbutler.models import Edition, Subscription
from depotbutler.publications import PublicationConfig
from depotbutler.settings import Settings
from depotbutler.utils.logger import get_logger

settings = Settings()
logger = get_logger(__name__)


class HttpxBoersenmedienClient:
    """HTTPX-based client for boersenmedien.com using cookie authentication."""

    def __init__(self):
        self.base_url = settings.boersenmedien.base_url
        self.client: Optional[httpx.AsyncClient] = None
        self.subscriptions: list[Subscription] = []

    async def login(self) -> int:
        """
        Ensure authenticated session using cookie from MongoDB.
        """
        logger.info("Authenticating with boersenmedien.com...")

        try:
            # Get cookie from MongoDB
            mongodb = await get_mongodb_service()
            
            # Check cookie expiration
            expiration_info = await mongodb.get_cookie_expiration_info()
            if expiration_info:
                expires_at = expiration_info.get("expires_at")
                days_remaining = expiration_info.get("days_remaining")
                is_expired = expiration_info.get("is_expired")

                if is_expired:
                    logger.error("❌ Cookie in MongoDB has EXPIRED!")
                    logger.error(f"   Expired on: {expires_at}")
                    logger.error(
                        "   Please update the cookie using: uv run python scripts/update_cookie_mongodb.py"
                    )
                    raise Exception("Cookie expired")
                elif days_remaining is not None and days_remaining <= 3:
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
                logger.error("1. Login to https://login.boersenmedien.com/ in your browser")
                logger.error("2. Copy the .AspNetCore.Cookies value from DevTools")
                logger.error("3. Run the cookie update script")
                logger.error("=" * 70)
                raise Exception("Authentication cookies not found")

            logger.info(f"✓ Loaded cookie from MongoDB (length: {len(cookie_value)})")

            # Create HTTPX client with cookie
            cookies = {
                ".AspNetCore.Cookies": cookie_value
            }

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
            }

            self.client = httpx.AsyncClient(
                cookies=cookies,
                headers=headers,
                follow_redirects=True,
                timeout=30.0
            )

            logger.info("✓ Authenticated successfully")
            return 200  # Success

        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise

    async def discover_subscriptions(self) -> list[Subscription]:
        """
        Auto-discover all active subscriptions from account.
        """
        if not self.client:
            raise Exception("Must call login() first")

        subscriptions_url = f"{self.base_url}/produkte/abonnements"

        try:
            response = await self.client.get(subscriptions_url)

            if response.status_code != 200:
                logger.error(f"Failed to access subscriptions page: {response.status_code}")
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

                    # Find "Ausgaben herunterladen" link for editions
                    links = item.find_all("a", href=True)
                    content_link = None
                    for link in links:
                        link_text = link.get_text(strip=True).lower()
                        if "ausgaben" in link_text or "herunterladen" in link_text:
                            content_link = link
                            break

                    if not content_link:
                        logger.warning(f"No editions link found for {name}")
                        continue

                    content_url = str(content_link["href"])
                    if not content_url.startswith("http"):
                        content_url = self.base_url + content_url

                    subscription = Subscription(
                        subscription_number=subscription_number,
                        subscription_id=subscription_id,
                        name=name,
                        content_url=content_url,
                    )

                    discovered.append(subscription)
                    logger.info(f"✓ Found subscription: {name} (ID: {subscription_id})")

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
    ) -> Optional[Edition]:
        """Get the latest edition for a publication."""
        if not self.client:
            raise Exception("Must call login() first")

        try:
            response = await self.client.get(publication.content_url)

            if response.status_code != 200:
                logger.error(f"Failed to access editions page: {response.status_code}")
                return None

            soup = BeautifulSoup(response.text, "html.parser")

            # Find the first edition article
            edition_item = soup.find("article", class_="edition-item")
            if not edition_item:
                logger.warning("No edition items found on page")
                return None

            # Extract title
            title_elem = edition_item.find("h1")
            if not title_elem:
                logger.warning("No h1 title found in edition article")
                return None

            title = title_elem.get_text(strip=True)

            # Extract details URL
            details_link = edition_item.find("a", href=True)
            if not details_link:
                logger.warning("No details link found in edition article")
                return None

            details_url = str(details_link["href"])
            if not details_url.startswith("http"):
                details_url = self.base_url + details_url

            # Extract publication date from time element
            publication_date = ""
            time_elem = edition_item.find("time")
            if time_elem and time_elem.get("datetime"):
                datetime_value = str(time_elem["datetime"])
                publication_date = datetime_value.split("T")[0]
                logger.info(f"Extracted publication date: {publication_date}")
            else:
                logger.warning(
                    "No time element found in edition item, will fetch from details page"
                )

            # Extract download URL
            download_link = edition_item.find("a", href=True, string="Download")
            if not download_link:
                logger.warning("No download link found in edition article")
                return None

            download_url = str(download_link["href"])
            if not download_url.startswith("http"):
                download_url = self.base_url + download_url

            edition = Edition(
                title=title,
                details_url=details_url,
                download_url=download_url,
                publication_date=publication_date,
            )

            logger.info(f"Found latest edition: {title}")
            return edition

        except Exception as e:
            logger.error(f"Failed to get latest edition: {e}")
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

    async def download_edition(self, edition: Edition, filepath: str):
        """Download edition PDF to local file."""
        if not self.client:
            raise Exception("Must call login() first")

        try:
            logger.info(f"Downloading from: {edition.download_url}")
            
            response = await self.client.get(edition.download_url)

            if response.status_code != 200:
                raise Exception(f"Download failed with status {response.status_code}")

            # Write PDF to file
            with open(filepath, 'wb') as f:
                f.write(response.content)

            logger.info(f"✓ Downloaded PDF to: {filepath}")

        except Exception as e:
            logger.error(f"Failed to download PDF: {e}")
            raise

    async def close(self):
        """Cleanup HTTP client resources."""
        if self.client:
            await self.client.aclose()
