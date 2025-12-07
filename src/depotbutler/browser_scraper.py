"""Browser-based scraper with manual login and session persistence"""

import asyncio
import json
import os
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from patchright.async_api import Browser, BrowserContext, Page, async_playwright

from depotbutler.db.mongodb import get_mongodb_service
from depotbutler.settings import Settings
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


class BrowserScraper:
    """Scraper that handles Cloudflare-protected sites with manual login and session reuse"""

    def __init__(self, settings: Settings):
        self.settings = settings

    async def _get_cookie_from_mongodb(self) -> str | None:
        """Get authentication cookie from MongoDB (preferred method)."""
        try:
            logger.info("Attempting to load cookie from MongoDB...")
            mongodb = await get_mongodb_service()

            # Check cookie expiration first
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
                    return None
                elif days_remaining is not None and days_remaining <= 3:
                    logger.warning("⚠️  Cookie will expire soon!")
                    logger.warning(f"   Expires on: {expires_at}")
                    logger.warning(f"   Days remaining: {days_remaining}")
                    logger.warning(
                        "   Consider updating the cookie soon using: uv run python scripts/update_cookie_mongodb.py"
                    )
                elif expires_at:
                    logger.info(
                        f"Cookie expires on {expires_at} ({days_remaining} days remaining)"
                    )

            cookie_value = await mongodb.get_auth_cookie()

            if cookie_value:
                logger.info(
                    f"✓ Loaded authentication cookie from MongoDB (length: {len(cookie_value)})"
                )
                return cookie_value
            else:
                logger.info("No cookie found in MongoDB")
                return None

        except Exception as e:
            logger.error(f"Failed to load cookie from MongoDB: {type(e).__name__}: {e}")
            logger.error(traceback.format_exc())
            return None

    async def _load_cookies(self) -> list[dict] | None:
        """Load cookies from MongoDB (preferred), Key Vault (fallback), or local file (development)."""
        logger.info("=== _load_cookies() called ===")

        # Try MongoDB first (preferred for production and development)
        cookie_value = await self._get_cookie_from_mongodb()
        if cookie_value:
            logger.info("Got cookie from MongoDB, creating cookie structure...")
            # Create cookie structure from MongoDB value
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

        logger.error("No cookie found in MongoDB")
        logger.error(
            "Please update the cookie using: uv run python scripts/update_cookie_mongodb.py"
        )
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

                # Save cookies to MongoDB for future use
                cookies = await context.cookies()

                # Extract the auth cookie and save to MongoDB
                auth_cookie = next(
                    (c for c in cookies if c["name"] == ".AspNetCore.Cookies"), None
                )
                if auth_cookie:
                    cookie_value = auth_cookie["value"]
                    expires_unix = auth_cookie.get("expires")
                    expires_at = None
                    if expires_unix:
                        expires_at = datetime.fromtimestamp(
                            expires_unix, tz=timezone.utc
                        )

                    mongodb = await get_mongodb_service()
                    success = await mongodb.update_auth_cookie(
                        cookie_value, expires_at, "manual-login"
                    )

                    if success:
                        logger.info("✓ Session saved to MongoDB")
                    else:
                        logger.warning("⚠️  Failed to save session to MongoDB")
                else:
                    logger.warning("⚠️  Could not find auth cookie to save")

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
        # Try to load existing cookies from MongoDB, Key Vault, or local file
        cookies = await self._load_cookies()
        if not cookies:
            logger.error("No cookies available from MongoDB, Key Vault, or local file")
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
