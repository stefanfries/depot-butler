"""Browser-based scraper with manual login and session persistence"""

import asyncio
import json
import os
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from depotbutler.settings import Settings
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


class BrowserScraper:
    """Scraper that handles Cloudflare-protected sites with manual login and session reuse"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.cookies_file = Path("data/browser_cookies.json")
        self.cookies_file.parent.mkdir(exist_ok=True)

    def _get_cookie_from_keyvault(self) -> str | None:
        """Get authentication cookie from Azure Key Vault (production)."""
        try:
            # Only use Key Vault in production (when AZURE_KEY_VAULT_URL is set)
            key_vault_url = os.getenv("AZURE_KEY_VAULT_URL")
            if not key_vault_url:
                logger.info("AZURE_KEY_VAULT_URL not set, skipping Key Vault")
                return None

            logger.info(f"Attempting to load cookie from Key Vault: {key_vault_url}")

            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient

            logger.info("Creating DefaultAzureCredential...")
            credential = DefaultAzureCredential()

            logger.info("Creating SecretClient...")
            client = SecretClient(vault_url=key_vault_url, credential=credential)

            logger.info("Fetching secret 'boersenmedien-session-cookie'...")
            secret = client.get_secret("boersenmedien-session-cookie")
            cookie_value = secret.value

            if cookie_value:
                logger.info(
                    f"✓ Loaded authentication cookie from Azure Key Vault (length: {len(cookie_value)})"
                )
                return cookie_value
            else:
                logger.error("Cookie value is empty in Key Vault")

        except Exception as e:
            logger.error(
                f"Failed to load cookie from Key Vault: {type(e).__name__}: {e}"
            )
            logger.error(traceback.format_exc())

        return None

    def _load_cookies(self) -> list[dict] | None:
        """Load cookies from Key Vault (production) or local file (development)."""
        logger.info("=== _load_cookies() called ===")

        # Try Key Vault first (production)
        cookie_value = self._get_cookie_from_keyvault()
        if cookie_value:
            logger.info(f"Got cookie from Key Vault, creating cookie structure...")
            # Create cookie structure from Key Vault value
            expires = datetime.now() + timedelta(days=14)

            return [
                {
                    "name": ".AspNetCore.Cookies",
                    "value": cookie_value,
                    "domain": ".boersenmedien.com",
                    "path": "/",
                    "expires": int(expires.timestamp()),
                    "httpOnly": True,
                    "secure": True,
                    "sameSite": "Lax",
                }
            ]

        logger.info("No cookie from Key Vault, checking local file...")

        # Fall back to local file (development)
        if self.cookies_file.exists():
            logger.info("Loading authentication cookie from local file")
            with open(self.cookies_file, "r", encoding="utf-8") as f:
                cookies_data = json.load(f)
                # Handle both single object and array formats
                if isinstance(cookies_data, list):
                    return cookies_data
                else:
                    return [cookies_data]

        logger.error("No cookies found - neither Key Vault nor local file")
        return None

    async def _is_logged_in(self, page: Page) -> bool:
        """Check if currently logged in by attempting to access subscription page"""
        try:
            current_url = page.url
            logger.info(f"Checking login status. Current URL: {current_url}")

            # If already on a konto.boersenmedien.com page (not login), consider logged in
            if (
                "konto.boersenmedien.com" in current_url
                and "login" not in current_url.lower()
            ):
                logger.info("✓ Already on authenticated konto page")
                return True

            # Try to navigate to subscription page
            logger.info("Navigating to subscription page to verify login...")
            await page.goto(
                "https://konto.boersenmedien.com/produkte/abonnements",
                wait_until="domcontentloaded",
                timeout=10000,
            )

            final_url = page.url
            logger.info(f"Final URL after navigation: {final_url}")

            # If we're redirected to login, we're not logged in
            if "login" in final_url.lower():
                logger.warning("Redirected to login page - not logged in")
                return False

            # Check for subscription content
            content = await page.content()
            has_content = "abonnement" in content.lower()

            if has_content:
                logger.info("✓ Found subscription content - logged in")
            else:
                logger.warning("No subscription content found on page")

            return has_content

        except Exception as e:
            logger.warning(f"Error checking login status: {e}")
            return False

    async def _perform_manual_login(self, context: BrowserContext) -> bool:
        """Open browser for user to manually complete login"""
        page = await context.new_page()

        try:
            logger.info("Opening login page for manual authentication...")
            logger.info("=" * 60)
            logger.info("INSTRUCTIONS:")
            logger.info("1. Enter your email and password in the browser window")
            logger.info("2. Wait for Cloudflare challenge to complete")
            logger.info("3. Click the login button")
            logger.info("4. Wait until you see the subscription page")
            logger.info("5. Come back here and press Enter to save the session")
            logger.info("=" * 60)

            # Navigate to login page
            await page.goto(
                "https://login.boersenmedien.com/", wait_until="networkidle"
            )

            # Wait for user to complete login manually
            # Use input() to block until user presses Enter
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: input(
                    "\nPress Enter after you've completed the login and see the subscription page... "
                ),
            )

            # Now check if login was successful
            if await self._is_logged_in(page):
                logger.info("✓ Login successful!")

                # Save cookies for future use
                cookies = await context.cookies()
                with open(self.cookies_file, "w") as f:
                    json.dump(cookies, f, indent=2)
                logger.info(f"✓ Session saved to {self.cookies_file}")

                await page.close()
                return True
            else:
                logger.error("❌ Login verification failed. Please try again.")
                await page.close()
                return False

        except Exception as e:
            logger.error(f"Error during manual login: {e}")
            await page.close()
            return False

    async def ensure_authenticated(self) -> tuple[Browser, BrowserContext]:
        """Ensure we have an authenticated session, performing manual login if needed

        Returns:
            Tuple of (browser, context) - caller is responsible for closing browser
        """
        # Try to load existing cookies from Key Vault or local file
        cookies = self._load_cookies()
        if not cookies:
            logger.error("No cookies available from Key Vault or local file")
            raise Exception(
                "No authentication cookies found. Cannot proceed in production environment."
            )

        p = await async_playwright().start()

        # Use persistent context (real browser profile) to better bypass Cloudflare
        user_data_dir = Path("data/browser_profile")
        user_data_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Launching browser with profile: {user_data_dir}")

        # Use Chromium (available in container), not Edge
        # In production (Azure), use headless mode
        is_production = bool(os.getenv("AZURE_KEY_VAULT_URL"))

        try:
            context = await p.chromium.launch_persistent_context(
                str(user_data_dir),
                headless=is_production,  # Headless in production
                viewport={"width": 1920, "height": 1080},
                locale="de-DE",
            )
        except Exception as e:
            logger.error(f"Failed to launch browser: {e}")
            raise Exception(f"Failed to launch browser: {e}") from e

        browser = context.browser

        logger.info("Found existing session cookies, attempting to load...")
        try:
            await context.add_cookies(cookies)

            # Verify session is still valid
            page = await context.new_page()
            if await self._is_logged_in(page):
                logger.info("✓ Existing session is valid!")
                await page.close()
                return browser, context
            else:
                logger.error("Session cookies are expired or invalid")
                await page.close()
                await browser.close()
                raise Exception(
                    "Session expired. Please refresh cookies using upload_cookie_to_keyvault.py"
                )
        except Exception as e:
            logger.error(f"Failed to load existing session: {e}")
            if browser:
                await browser.close()
            raise

    async def discover_subscriptions(self) -> list[dict[str, Any]]:
        """Get list of subscriptions from the account page"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                locale="de-DE",
            )

            # Load saved cookies
            if self.cookies_file.exists():
                with open(self.cookies_file, "r") as f:
                    cookies = json.load(f)
                await context.add_cookies(cookies)
            else:
                logger.error("No saved session found. Please run authentication first.")
                await browser.close()
                return []

            page = await context.new_page()

            try:
                # Go to subscriptions page
                await page.goto(
                    "https://konto.boersenmedien.com/produkte/abonnements",
                    wait_until="networkidle",
                )

                # Check if we're still logged in
                if "login" in page.url.lower():
                    logger.error("Session expired. Please re-authenticate.")
                    await browser.close()
                    return []

                # Parse subscriptions
                content = await page.content()
                soup = BeautifulSoup(content, "html.parser")

                subscriptions = []
                # Look for subscription elements - adjust selectors as needed
                sub_elements = soup.find_all(
                    "div", class_="subscription-item"
                )  # Example selector

                for elem in sub_elements:
                    # Extract subscription details
                    title = elem.find("h3")
                    title_text = title.get_text(strip=True) if title else "Unknown"

                    subscriptions.append(
                        {
                            "title": title_text,
                            "url": f"https://konto.boersenmedien.com/produkte/abonnements/{title_text}",
                        }
                    )

                logger.info(f"Found {len(subscriptions)} subscriptions")
                return subscriptions

            finally:
                await browser.close()
