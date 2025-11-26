"""
Browser-based client for boersenmedien.com that bypasses Cloudflare protection.
Uses manually-exported cookies for authentication.
"""
from datetime import datetime
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup
from playwright.async_api import Browser, BrowserContext, Page

from depotbutler.browser_scraper import BrowserScraper
from depotbutler.models import Edition, Subscription
from depotbutler.publications import PublicationConfig
from depotbutler.settings import Settings
from depotbutler.utils.logger import get_logger

settings = Settings()
logger = get_logger(__name__)


class BrowserBoersenmedienClient:
    """Browser-based client for boersenmedien.com using manual cookie authentication."""

    def __init__(self):
        self.base_url = settings.boersenmedien.base_url
        self.scraper = BrowserScraper(settings)
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.subscriptions: list[Subscription] = []

    async def login(self) -> int:
        """
        Ensure authenticated session using manually-exported cookies.
        Opens browser for manual login if no valid session exists.
        """
        logger.info("Authenticating with boersenmedien.com...")
        
        # Get authenticated browser session (handles both Key Vault and local file)
        try:
            self.browser, self.context = await self.scraper.ensure_authenticated()
            logger.info("✓ Authenticated successfully")
            return 200  # Success
        except Exception as e:
            logger.error("=" * 70)
            logger.error("NO COOKIES FOUND!")
            logger.error("=" * 70)
            logger.error("You need to export cookies from your browser first.")
            logger.error("Run: uv run python quick_cookie_import.py")
            logger.error("")
            logger.error("Steps:")
            logger.error("1. Login to https://login.boersenmedien.com/ in your browser")
            logger.error("2. Copy the .AspNetCore.Cookies value from DevTools")
            logger.error("3. Paste it into quick_cookie_import.py")
            logger.error("=" * 70)
            raise Exception("Authentication cookies not found. Run quick_cookie_import.py first.") from e

    async def discover_subscriptions(self) -> list[Subscription]:
        """
        Auto-discover all active subscriptions from account.
        """
        if not self.context:
            raise Exception("Must call login() first")

        subscriptions_url = f"{self.base_url}/produkte/abonnements"
        
        try:
            page = await self.context.new_page()
            await page.goto(subscriptions_url, wait_until="networkidle")
            
            content = await page.content()
            soup = BeautifulSoup(content, "html.parser")
            
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
                        logger.warning(f"No h2 found for subscription {subscription_id}")
                        continue
                    
                    # Get text without the badge span
                    name = name_elem.get_text(strip=True)
                    # Remove "Aktiv" or "Inaktiv" badge text if present
                    name = name.replace("Aktiv", "").replace("Inaktiv", "").strip()

                    # Find "Ausgaben herunterladen" link for editions
                    # The text is inside the <a> tag directly
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

            await page.close()
            self.subscriptions = discovered
            logger.info(f"✓ Discovered {len(discovered)} total subscriptions")
            return discovered

        except Exception as e:
            logger.error(f"Failed to discover subscriptions: {e}")
            return []

    async def get_latest_edition(self, publication: PublicationConfig) -> Optional[Edition]:
        """Get the latest edition for a publication."""
        if not self.context:
            raise Exception("Must call login() first")

        try:
            # Find matching subscription
            subscription = next(
                (s for s in self.subscriptions if publication.name.lower() in s.name.lower()),
                None
            )

            if not subscription:
                logger.error(f"No subscription found for: {publication.name}")
                return None

            page = await self.context.new_page()
            await page.goto(subscription.content_url, wait_until="networkidle")

            content = await page.content()
            soup = BeautifulSoup(content, "html.parser")

            # Find latest edition (first article in list)
            edition_item = soup.find("article", class_="list-item")
            if not edition_item:
                logger.warning("No edition articles found on page")
                await page.close()
                return None

            # Extract title from h2
            title_elem = edition_item.find("h2")
            if not title_elem:
                logger.warning("No title found in edition article")
                await page.close()
                return None
            
            title_link = title_elem.find("a")
            title = title_link.get_text(strip=True) if title_link else title_elem.get_text(strip=True)

            # Extract details URL from title link
            details_url = ""
            if title_link and title_link.get("href"):
                details_url = str(title_link["href"])
                if not details_url.startswith("http"):
                    details_url = self.base_url + details_url

            # Extract publication date from time element
            publication_date = ""
            time_elem = edition_item.find("time")
            if time_elem and time_elem.get("datetime"):
                # Extract date from datetime attribute (format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
                datetime_value = str(time_elem["datetime"])
                publication_date = datetime_value.split("T")[0]  # Get just the date part
                logger.info(f"Extracted publication date: {publication_date}")
            else:
                logger.warning("No time element found in edition item, will fetch from details page")

            # Extract download URL
            download_link = edition_item.find("a", href=True, string="Download")
            if not download_link:
                logger.warning("No download link found in edition article")
                await page.close()
                return None

            download_url = str(download_link["href"])
            if not download_url.startswith("http"):
                download_url = self.base_url + download_url

            await page.close()

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
        if not self.context:
            raise Exception("Must call login() first")
        
        # If we already have a publication date, return it
        if edition.publication_date:
            return edition
        
        # If no details URL, use current date as fallback
        if not edition.details_url:
            edition.publication_date = datetime.now().strftime("%Y-%m-%d")
            logger.warning(f"No details URL available, using current date: {edition.publication_date}")
            return edition
        
        try:
            page = await self.context.new_page()
            await page.goto(edition.details_url, wait_until="networkidle")
            
            content = await page.content()
            soup = BeautifulSoup(content, "html.parser")
            
            # Look for time element with datetime attribute
            time_elem = soup.find("time")
            if time_elem and time_elem.get("datetime"):
                datetime_value = str(time_elem["datetime"])
                edition.publication_date = datetime_value.split("T")[0]
                logger.info(f"Extracted publication date from details page: {edition.publication_date}")
            else:
                # Fallback to current date
                edition.publication_date = datetime.now().strftime("%Y-%m-%d")
                logger.warning(f"No date found on details page, using current date: {edition.publication_date}")
            
            await page.close()
            return edition
            
        except Exception as e:
            logger.error(f"Failed to get publication date: {e}")
            # Fallback to current date
            edition.publication_date = datetime.now().strftime("%Y-%m-%d")
            return edition

    async def download_edition(self, edition: Edition, filepath: str):
        """Download edition PDF to local file."""
        if not self.context:
            raise Exception("Must call login() first")

        try:
            page = await self.context.new_page()
            
            # Set up download handler and trigger via evaluate
            async with page.expect_download(timeout=30000) as download_info:
                # Navigate to a page (any page) to have context
                await page.goto("https://konto.boersenmedien.com/produkte/abonnements")
                # Trigger download by creating and clicking a link
                await page.evaluate(f"""
                    (url) => {{
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = '';
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                    }}
                """, edition.download_url)
            
            download = await download_info.value
            await download.save_as(filepath)
            await page.close()
            
            logger.info(f"✓ Downloaded PDF to: {filepath}")

        except Exception as e:
            logger.error(f"Failed to download PDF: {e}")
            raise

    async def close(self):
        """Cleanup browser resources."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
