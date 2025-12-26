"""
Test website crawling capability for Megatrend-Folger editions.

This script validates that we can:
1. Access boersenmedien.com ausgaben pages
2. Extract metadata (title, issue, date, download URL)
3. Paginate through all available editions
4. Estimate total available editions

Run: uv run python scripts/validation/test_website_crawl.py
"""

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


import httpx
from bs4 import BeautifulSoup
from motor.motor_asyncio import AsyncIOMotorClient

from depotbutler.settings import Settings
from depotbutler.utils.logger import get_logger

settings = Settings()

logger = get_logger(__name__)


async def get_cookie_from_mongodb() -> str:
    """Retrieve authentication cookie from MongoDB."""
    client = None
    try:
        client = AsyncIOMotorClient(settings.mongodb.connection_string)
        db = client[settings.mongodb.name]
        config_collection = db["config"]

        config = await config_collection.find_one({"_id": "auth_cookie"})

        if not config:
            logger.error("❌ No auth cookie found in MongoDB")
            return ""

        cookie = config.get("cookie_value", "")
        logger.info(f"✅ Cookie loaded from MongoDB (length: {len(cookie)})")
        return cookie

    except Exception as e:
        logger.error(f"❌ Failed to get cookie from MongoDB: {e}")
        return ""
    finally:
        if client:
            client.close()


async def test_website_access():
    """Test basic access to ausgaben pages."""
    logger.info("Testing website access...")

    # Base URL for Megatrend-Folger ausgaben
    base_url = "https://konto.boersenmedien.com/produkte/abonnements/2477462/AM-01029205/ausgaben"

    # Get cookie from MongoDB
    cookie_value = await get_cookie_from_mongodb()

    if not cookie_value:
        logger.warning(
            "⚠️ No cookie available - test may fail if authentication required"
        )

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    cookies = {".AspNetCore.Cookies": cookie_value}

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                base_url, headers=headers, cookies=cookies, follow_redirects=True
            )
            response.raise_for_status()
            logger.info(f"✅ Website accessible (status: {response.status_code})")
            return response.text
        except httpx.HTTPError as e:
            logger.error(f"❌ Failed to access website: {e}")
            raise


async def parse_edition_metadata(html: str) -> list[dict]:
    """Parse edition metadata from ausgaben page HTML."""
    logger.info("Parsing edition metadata...")

    soup = BeautifulSoup(html, "html.parser")
    editions = []

    # Find all edition cards (structure may vary - this is a placeholder)
    # We'll need to inspect actual HTML structure
    edition_elements = soup.find_all("div", class_="edition-card")  # Adjust selector

    for elem in edition_elements:
        try:
            # Extract data (adjust selectors based on actual HTML)
            title = elem.find("h3").text.strip() if elem.find("h3") else None
            issue = (
                elem.find("span", class_="issue").text.strip()
                if elem.find("span", class_="issue")
                else None
            )
            date_str = (
                elem.find("span", class_="date").text.strip()
                if elem.find("span", class_="date")
                else None
            )
            download_url = (
                elem.find("a", class_="download")["href"]
                if elem.find("a", class_="download")
                else None
            )

            if all([title, issue, date_str, download_url]):
                editions.append(
                    {
                        "title": title,
                        "issue": issue,
                        "date": date_str,
                        "download_url": download_url,
                    }
                )
        except Exception as e:
            logger.warning(f"Failed to parse edition element: {e}")
            continue

    logger.info(f"Parsed {len(editions)} editions from page")
    return editions


async def test_pagination():
    """Test pagination through all available pages."""
    logger.info("Testing pagination...")

    base_url = "https://konto.boersenmedien.com/produkte/abonnements/2477462/AM-01029205/ausgaben"

    # Get cookie from MongoDB config (would need to implement)
    cookie = ""  # TODO: Get from MongoDB config collection

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Cookie": cookie,
    }

    total_editions = 0
    page = 1
    max_pages = 20  # Safety limit

    async with httpx.AsyncClient(timeout=30.0) as client:
        while page <= max_pages:
            try:
                url = f"{base_url}?page={page}"
                response = await client.get(url, headers=headers, follow_redirects=True)
                response.raise_for_status()

                editions = await parse_edition_metadata(response.text)

                if not editions:
                    logger.info(f"No more editions found at page {page}")
                    break

                total_editions += len(editions)
                logger.info(
                    f"Page {page}: {len(editions)} editions (total: {total_editions})"
                )

                # Check if there's a "next page" link
                soup = BeautifulSoup(response.text, "html.parser")
                next_link = soup.find("a", class_="next-page")  # Adjust selector
                if not next_link:
                    logger.info("No next page link found - reached end")
                    break

                page += 1
                await asyncio.sleep(1)  # Be nice to the server

            except httpx.HTTPError as e:
                logger.error(f"Failed to fetch page {page}: {e}")
                break

    logger.info(f"✅ Total editions discovered: {total_editions}")
    return total_editions


async def test_download_url():
    """Test that download URLs are accessible."""
    logger.info("Testing download URL access...")

    # We'll test this after we have a real download URL from parsing
    logger.warning("⚠️ Download URL test requires actual parsed URL - skipping for now")
    return True


async def main():
    """Run all website crawling tests."""
    logger.info("=" * 60)
    logger.info("WEBSITE CRAWLING VALIDATION")
    logger.info("=" * 60)

    try:
        # Test 1: Basic access
        html = await test_website_access()

        # Test 2: Parse metadata from first page
        editions = await parse_edition_metadata(html)
        if editions:
            logger.info(f"✅ Successfully parsed {len(editions)} editions")
            logger.info(f"Sample edition: {editions[0]}")
        else:
            logger.warning("⚠️ No editions parsed - HTML structure may differ")
            logger.info("First 1000 chars of HTML:")
            logger.info(html[:1000])

            # Save full HTML for inspection
            debug_path = Path("data/tmp/debug_website.html")
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(html)
            logger.info(f"Full HTML saved to: {debug_path}")

        # Test 3: Pagination
        # total = await test_pagination()
        # Commented out to avoid excessive requests during initial test

        logger.info("=" * 60)
        logger.info("VALIDATION COMPLETE")
        logger.info("=" * 60)
        logger.info("\nNext steps:")
        logger.info("1. Inspect HTML structure if parsing failed")
        logger.info("2. Adjust selectors in parse_edition_metadata()")
        logger.info("3. Uncomment pagination test once parsing works")
        logger.info("4. Proceed to test_pdf_parsing.py")

    except Exception as e:
        logger.error(f"❌ Validation failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
