from typing import Optional

import httpx
from bs4 import BeautifulSoup

from depotbutler.models import Edition, Subscription
from depotbutler.publications import PublicationConfig
from depotbutler.settings import Settings
from depotbutler.utils.logger import get_logger

settings = Settings()
logger = get_logger(__name__)


class BoersenmedienClient:
    """Client for interacting with boersenmedien.com publications."""

    def __init__(self):
        self.base_url = settings.boersenmedien.base_url
        self.login_url = settings.boersenmedien.login_url
        self.username = settings.boersenmedien.username
        self.password = settings.boersenmedien.password
        self.client = httpx.AsyncClient(follow_redirects=True)
        self.subscriptions: list[Subscription] = []

    async def login(self) -> int:

        # Step 1: Get login page to retrieve cookies + hidden fields
        r = await self.client.get(self.login_url)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        token = soup.find("input", {"name": "__RequestVerificationToken"})
        if not token:
            raise ValueError("Could not find __RequestVerificationToken on login page")
        token = token["value"]

        # Step 2: Build form payload (all required hidden + credentials)
        payload = {
            "__RequestVerificationToken": token,
            "Username": self.username.get_secret_value(),
            "Password": self.password.get_secret_value(),
            "UsePassword": "True",
            "EmailEntered": "False",
            "Kmsi": "True",
            "RedirectUri": "",
            "ApiKey": "",
            "CancelUri": "",
        }

        # Step 3: Submit login form
        response = await self.client.post(self.login_url, data=payload)
        response.raise_for_status()

        # Step 4: Verify login success
        if "logout" in response.text.lower() or "abmelden" in response.text.lower():
            logger.info("✅ Login successful!")
        else:
            logger.error(
                f"❌ Login may have failed. Check credentials or token. Response URL: {response.url}"
            )
        return response.status_code

    async def discover_subscriptions(self) -> list[Subscription]:
        """
        Auto-discover all active subscriptions from account.
        Returns list of subscriptions with subscription_number, subscription_id, and content URLs.
        Returns empty list if discovery endpoint is not available.
        """
        subscriptions_url = f"{self.base_url}/produkte/abonnements"

        try:
            response = await self.client.get(subscriptions_url)
            response.raise_for_status()
        except Exception as e:
            logger.warning(
                f"Could not auto-discover subscriptions from {subscriptions_url}: {e}. "
                "Using hardcoded publication config instead."
            )
            self.subscriptions = []
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        discovered = []

        # Find all subscription items with data attributes
        subscription_items = soup.find_all("div", class_="subscription-item")

        for item in subscription_items:
            try:
                # Extract data attributes directly
                subscription_number = str(item.get("data-subscription-number", ""))
                subscription_id = str(item.get("data-subscription-id", ""))
                
                if not subscription_number or not subscription_id:
                    logger.warning("Subscription item missing data attributes")
                    continue

                # Extract subscription name from h2
                name_elem = item.find("h2")
                if not name_elem:
                    logger.warning(f"No h2 found for subscription {subscription_number}")
                    continue
                
                # Get text and remove badge (e.g., "Aktiv" or "Inaktiv")
                name_text = name_elem.get_text(strip=True)
                # Remove status badge text
                badge = name_elem.find("span", class_="badge")
                if badge:
                    badge_text = badge.get_text(strip=True)
                    name = name_text.replace(badge_text, "").strip()
                else:
                    name = name_text

                # Construct content URL
                content_url = f"{self.base_url}/produkte/abonnements/{subscription_id}/{subscription_number}/ausgaben"

                subscription = Subscription(
                    name=name,
                    subscription_number=subscription_number,
                    subscription_id=subscription_id,
                    content_url=content_url,
                )
                discovered.append(subscription)
                logger.info(f"📚 Discovered subscription: {name} ({subscription_number})")

            except Exception as e:
                logger.warning(f"Failed to parse subscription item: {e}")
                continue

        self.subscriptions = discovered

        # Log summary of discovered subscriptions
        if discovered:
            logger.info(f"✅ Found {len(discovered)} subscription(s):")
            for sub in discovered:
                logger.info(
                    f"  - {sub.name} (ID: {sub.subscription_id}, Number: {sub.subscription_number})"
                )
        else:
            logger.warning("⚠️  No subscriptions discovered from the page")

        return discovered

    def get_subscription(
        self, publication: PublicationConfig
    ) -> Optional[Subscription]:
        """
        Get subscription for a specific publication config.
        Matches by subscription_number or name.
        """
        if not self.subscriptions:
            logger.warning(
                "No subscriptions discovered yet. Call discover_subscriptions() first."
            )
            return None

        # Try to match by subscription_number if provided
        if publication.subscription_number:
            for sub in self.subscriptions:
                if sub.subscription_number == publication.subscription_number:
                    return sub

        # Try to match by name (fuzzy match)
        for sub in self.subscriptions:
            if publication.name.lower() in sub.name.lower():
                return sub

        logger.warning(f"No subscription found for publication: {publication.name}")
        return None

    async def get_latest_edition(
        self, subscription: Subscription | PublicationConfig
    ) -> Edition:
        """
        Fetch the latest edition info for a subscription or publication.

        Args:
            subscription: Either a Subscription object or PublicationConfig
                         If PublicationConfig, will try to find matching subscription

        Returns:
            Edition object with latest edition info
        """
        # Handle PublicationConfig - convert to Subscription or construct URL
        if isinstance(subscription, PublicationConfig):
            # If PublicationConfig has hardcoded subscription_number and subscription_id, use them directly
            if subscription.subscription_number and subscription.subscription_id:
                content_url = f"{self.base_url}/produkte/abonnements/{subscription.subscription_id}/{subscription.subscription_number}/ausgaben"
                logger.info(
                    f"Using hardcoded subscription info for {subscription.name}"
                )
            else:
                # Try to find matching subscription from discovered list
                sub = self.get_subscription(subscription)
                if not sub:
                    raise ValueError(
                        f"Could not find subscription for publication: {subscription.name}. "
                        "Either provide subscription_number and subscription_id in PublicationConfig or call discover_subscriptions() first."
                    )
                content_url = sub.content_url
        else:
            content_url = subscription.content_url

        response = await self.client.get(content_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        article = soup.find("article", class_="list-item universal-list-item")

        if not article:
            raise ValueError(f"No edition found at {content_url}")

        title_elem = article.find("h2")
        if title_elem:
            title_link = title_elem.find("a")
            title = title_link.text.strip() if title_link else "Unknown"
        else:
            title = "Unknown"

        header_elem = article.find("header")
        if header_elem:
            details_link = header_elem.find("a", href=True)
            details_url = (
                f"{self.base_url}{details_link['href']}" if details_link else ""
            )
        else:
            details_url = ""

        footer_elem = article.find("footer")
        if footer_elem:
            download_link = footer_elem.find("a", href=True)
            download_url = (
                f"{self.base_url}{download_link['href']}" if download_link else ""
            )
        else:
            download_url = ""

        return Edition(
            title=title,
            details_url=details_url,
            download_url=download_url,
            publication_date="unknown",
        )

    async def get_publication_date(self, edition: Edition) -> Edition:
        """Get the publication date of the latest edition."""
        response = await self.client.get(edition.details_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        time_elem = soup.find("time")
        if time_elem and time_elem.get("datetime"):
            edition.publication_date = str(time_elem["datetime"])
        else:
            edition.publication_date = "unknown"
        return edition

    async def download_edition(
        self, edition: Edition, dest_path: str
    ) -> httpx.Response:
        """Download the PDF file."""
        response = await self.client.get(edition.download_url)
        response.raise_for_status()

        with open(dest_path, "wb") as f:
            f.write(response.content)
        logger.info(f"✅ PDF downloaded to {dest_path}")
        return response

    async def close(self):
        await self.client.aclose()
