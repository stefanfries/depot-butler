"""Browser-based scraper with manual login and session persistence"""
import asyncio
import json
import os
from pathlib import Path
from typing import Any
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from bs4 import BeautifulSoup

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
                return None
            
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient
            
            credential = DefaultAzureCredential()
            client = SecretClient(vault_url=key_vault_url, credential=credential)
            
            # Try to get the cookie from Key Vault
            secret = client.get_secret("boersenmedien-session-cookie")
            cookie_value = secret.value
            
            if cookie_value:
                logger.info("✓ Loaded authentication cookie from Azure Key Vault")
                return cookie_value
            
        except Exception as e:
            logger.warning(f"Could not load cookie from Key Vault: {e}")
        
        return None
    
    def _load_cookies(self) -> list[dict] | None:
        """Load cookies from Key Vault (production) or local file (development)."""
        # Try Key Vault first (production)
        cookie_value = self._get_cookie_from_keyvault()
        if cookie_value:
            # Create cookie structure from Key Vault value
            from datetime import datetime, timedelta
            expires = datetime.now() + timedelta(days=14)
            
            return [{
                "name": ".AspNetCore.Cookies",
                "value": cookie_value,
                "domain": ".boersenmedien.com",
                "path": "/",
                "expires": int(expires.timestamp()),
                "httpOnly": True,
                "secure": True,
                "sameSite": "Lax"
            }]
        
        # Fall back to local file (development)
        if self.cookies_file.exists():
            logger.info("Loading authentication cookie from local file")
            with open(self.cookies_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        return None
        
    async def _is_logged_in(self, page: Page) -> bool:
        """Check if currently logged in by attempting to access subscription page"""
        try:
            current_url = page.url
            logger.info(f"Checking login status. Current URL: {current_url}")
            
            # If already on a konto.boersenmedien.com page (not login), consider logged in
            if "konto.boersenmedien.com" in current_url and "login" not in current_url.lower():
                logger.info("✓ Already on authenticated konto page")
                return True
            
            # Try to navigate to subscription page
            logger.info("Navigating to subscription page to verify login...")
            await page.goto(
                "https://konto.boersenmedien.com/produkte/abonnements",
                wait_until="domcontentloaded",
                timeout=10000
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
            await page.goto("https://login.boersenmedien.com/", wait_until="networkidle")
            
            # Wait for user to complete login manually
            # Use input() to block until user presses Enter
            await asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: input("\nPress Enter after you've completed the login and see the subscription page... ")
            )
            
            # Now check if login was successful
            if await self._is_logged_in(page):
                logger.info("✓ Login successful!")
                
                # Save cookies for future use
                cookies = await context.cookies()
                with open(self.cookies_file, 'w') as f:
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
        p = await async_playwright().start()
        
        # Use persistent context (real browser profile) to better bypass Cloudflare
        user_data_dir = Path("data/browser_profile")
        user_data_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Launching browser with profile: {user_data_dir}")
        
        # Try to use actual Chrome/Edge instead of Playwright's Chromium
        # This can help bypass Cloudflare detection
        context = await p.chromium.launch_persistent_context(
            str(user_data_dir),
            headless=False,
            channel="msedge",  # Use actual Edge browser
            viewport={"width": 1920, "height": 1080},
            locale="de-DE",
        )
        
        browser = context.browser
        
        # Try to load existing cookies from Key Vault or local file
        cookies = self._load_cookies()
        if cookies:
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
                    logger.info("Session expired, manual login required")
                    await page.close()
            except Exception as e:
                logger.warning(f"Failed to load existing session: {e}")
        else:
            logger.info("No existing session found, manual login required")
        
        # Need manual login
        if await self._perform_manual_login(context):
            return browser, context
        else:
            await browser.close()
            raise Exception("Failed to authenticate")
    
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
                with open(self.cookies_file, 'r') as f:
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
                    wait_until="networkidle"
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
                sub_elements = soup.find_all("div", class_="subscription-item")  # Example selector
                
                for elem in sub_elements:
                    # Extract subscription details
                    title = elem.find("h3")
                    title_text = title.get_text(strip=True) if title else "Unknown"
                    
                    subscriptions.append({
                        "title": title_text,
                        "url": f"https://konto.boersenmedien.com/produkte/abonnements/{title_text}",
                    })
                
                logger.info(f"Found {len(subscriptions)} subscriptions")
                return subscriptions
                
            finally:
                await browser.close()
