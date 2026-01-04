"""
Web URL Sync Script

Enriches existing MongoDB editions with download URLs from the website.
This script ONLY updates existing entries - it never creates new ones.

Architecture:
    - OneDrive is the single source of truth for archived PDFs
    - Web sync runs AFTER OneDrive import to add download_url fields
    - Only updates entries that exist in MongoDB (imported from OneDrive)
    - Never creates new entries or downloads PDFs

Usage:
    # Dry-run (discover and match, no updates)
    uv run python scripts/sync_web_urls.py --dry-run

    # Sync specific publication
    uv run python scripts/sync_web_urls.py --publication megatrend-folger

    # Full sync (all publications)
    uv run python scripts/sync_web_urls.py

Features:
    - Discovers available editions from website
    - Matches by publication_date + publication_id
    - Updates download_url for matched entries
    - Dry-run mode for testing
    - Never creates new MongoDB entries
    - Reports unmatched web editions (available but not in archive)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from bs4 import BeautifulSoup

from depotbutler.db.mongodb import MongoDBService, get_mongodb_service
from depotbutler.httpx_client import HttpxBoersenmedienClient
from depotbutler.models import Edition, PublicationConfig
from depotbutler.services.blob_storage_service import BlobStorageService
from depotbutler.settings import Settings
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)
settings = Settings()


class WebUrlSync:
    """Syncs download URLs from website to existing MongoDB entries."""

    def __init__(
        self,
        dry_run: bool = False,
        publication_id: str | None = None,
        max_pages: int | None = None,
    ) -> None:
        self.dry_run = dry_run
        self.publication_id = publication_id
        self.max_pages = max_pages

        self.client: HttpxBoersenmedienClient | None = None
        self.mongodb: MongoDBService
        self.blob_storage: BlobStorageService | None = None

        # Statistics
        self.stats = {
            "web_discovered": 0,
            "mongodb_entries": 0,
            "matched": 0,
            "updated": 0,
            "unmatched_web": 0,  # On web but not in MongoDB
            "unmatched_mongodb": 0,  # In MongoDB but not on web
            "failed": 0,
        }

    async def __aenter__(self) -> WebUrlSync:
        """Initialize services."""
        logger.info("Initializing web URL sync...")

        # MongoDB
        mongodb_service = await get_mongodb_service()
        if not mongodb_service:
            raise RuntimeError("Failed to initialize MongoDB service")
        self.mongodb = mongodb_service
        logger.info("✓ MongoDB connected")

        # HTTP Client
        self.client = HttpxBoersenmedienClient()
        await self.client.login()
        logger.info("✓ HTTP client initialized")

        # Discover active subscriptions
        await self.client.discover_subscriptions()
        logger.info(f"✓ Discovered {len(self.client.subscriptions)} subscriptions")

        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Cleanup services."""
        if self.client:
            await self.client.close()
        if self.mongodb:
            await self.mongodb.close()

    async def sync_all_publications(self) -> None:
        """Sync download URLs for all publications."""
        # Get active publications from MongoDB
        publications_cursor = self.mongodb.db["publications"].find({"active": True})
        publications = await publications_cursor.to_list(None)

        if not publications:
            logger.warning("No active publications found in MongoDB")
            return

        logger.info(f"Found {len(publications)} active publications")
        logger.info("")

        for pub_doc in publications:
            # Filter if specific publication requested
            if self.publication_id and pub_doc["publication_id"] != self.publication_id:
                continue

            # Create PublicationConfig from MongoDB document
            publication = PublicationConfig(
                id=pub_doc["publication_id"],
                name=pub_doc["name"],
                onedrive_folder=pub_doc.get("default_onedrive_folder", ""),
                subscription_number=pub_doc.get("subscription_number"),
                subscription_id=pub_doc.get("subscription_id"),
            )

            try:
                await self._sync_publication(publication)
            except Exception as e:
                logger.error(f"Failed to sync {publication.name}: {e}")
                self.stats["failed"] += 1

            logger.info("")

        self._print_summary()

    async def _sync_publication(self, publication: PublicationConfig) -> None:
        """Sync download URLs for a single publication."""
        logger.info("=" * 70)
        logger.info(f"SYNCING: {publication.name}")
        logger.info("=" * 70)

        # Step 1: Discover editions from website
        logger.info("Discovering editions from website...")
        web_by_issue = await self._discover_web_editions(publication)

        if not web_by_issue:
            logger.warning(f"No editions found on website for {publication.name}")
            return

        self.stats["web_discovered"] += len(web_by_issue)
        logger.info(f"✓ Found {len(web_by_issue)} editions on website")

        # Step 2: Get existing MongoDB entries
        logger.info("Loading MongoDB entries...")
        mongodb_entries = await self._get_mongodb_entries(publication.id)
        self.stats["mongodb_entries"] += len(mongodb_entries)
        logger.info(f"✓ Found {len(mongodb_entries)} entries in MongoDB")

        # Step 3: Match and update
        logger.info("")
        logger.info("Matching by publication_date...")

        # Create lookup dict: publication_date -> entry
        # Edition key format: YYYY-MM-DD_publication-name_II-YYYY
        # Example: 2025-12-18_megatrend-folger_51-2025
        # Extract publication_date from first part
        mongodb_by_date: dict[str, dict] = {}
        for entry in mongodb_entries:
            edition_key = entry["edition_key"]
            parts = edition_key.split("_")

            try:
                # First part is the publication_date: "YYYY-MM-DD"
                publication_date = parts[0]
                mongodb_by_date[publication_date] = entry
            except (ValueError, IndexError) as e:
                logger.warning(
                    f"Skipping entry with invalid edition_key format: {edition_key} ({e})"
                )
                continue

        # Match and update
        matched = 0
        updated = 0
        unmatched_web = []
        unmatched_mongodb = []

        # Process MongoDB entries (try to add download_url)
        for pub_date, mongo_entry in mongodb_by_date.items():
            web_edition = web_by_issue.get(pub_date)

            if web_edition:
                # Match found!
                matched += 1

                # Check if already has download_url
                if mongo_entry.get("download_url"):
                    logger.info(
                        f"  {pub_date} - Already has URL: {mongo_entry['edition_key']}"
                    )
                    continue

                # Update download_url
                logger.info(f"  {pub_date} - Updating: {mongo_entry['edition_key']}")
                logger.info(f"           URL: {web_edition.download_url}")

                if not self.dry_run:
                    await self._update_download_url(
                        mongo_entry["edition_key"],
                        web_edition.download_url,
                        mongo_entry.get("onedrive_path"),
                    )
                    updated += 1
                else:
                    logger.info("           [DRY-RUN] Would update")
                    updated += 1
            else:
                # In MongoDB but not on web
                unmatched_mongodb.append((pub_date, mongo_entry["edition_key"]))

        # Find editions on web but not in MongoDB
        for pub_date, web_edition in web_by_issue.items():
            if pub_date not in mongodb_by_date:
                unmatched_web.append((pub_date, web_edition.title))

        # Update stats
        self.stats["matched"] += matched
        self.stats["updated"] += updated
        self.stats["unmatched_web"] += len(unmatched_web)
        self.stats["unmatched_mongodb"] += len(unmatched_mongodb)

        # Report unmatched
        if unmatched_mongodb:
            logger.info("")
            logger.info(
                f"⚠ {len(unmatched_mongodb)} editions in MongoDB but NOT on web:"
            )
            for pub_date, edition_key in unmatched_mongodb[:10]:
                logger.info(f"    {pub_date} - {edition_key}")
            if len(unmatched_mongodb) > 10:
                logger.info(f"    ... and {len(unmatched_mongodb) - 10} more")

        if unmatched_web:
            logger.info("")
            logger.info(
                f"ℹ {len(unmatched_web)} editions on web but NOT in MongoDB (not archived):"
            )
            for pub_date, title in unmatched_web:
                logger.info(f"    {pub_date} - {title}")

        logger.info("")
        logger.info(f"✓ Matched: {matched}, Updated: {updated}")

    async def _discover_web_editions(
        self, publication: PublicationConfig
    ) -> dict[str, Edition]:
        """Discover all available editions for a publication from website.

        Returns:
            Dict mapping publication_date -> Edition
        """
        if not self.client:
            raise RuntimeError("Client not initialized")

        try:
            # Find subscription for this publication
            subscription = None
            for sub in self.client.subscriptions:
                if (
                    publication.name.lower() in sub.name.lower()
                    or sub.name.lower() in publication.name.lower()
                ):
                    subscription = sub
                    break

            if not subscription:
                logger.warning(f"No subscription found for {publication.name}")
                return {}

            editions_by_date: dict[str, Edition] = {}
            page = 1

            # Get base URL (same logic as collect_historical_pdfs.py)
            base_url = subscription.content_url
            if base_url.endswith("/ausgaben/1"):
                base_url = base_url[:-2]  # Remove the "/1"
            elif not base_url.endswith("/ausgaben") and "/ausgaben/" in base_url:
                base_url = base_url.split("/ausgaben")[0] + "/ausgaben"

            # Paginate through pages (limited by max_pages if set)
            while True:
                if self.max_pages and page > self.max_pages:
                    logger.info(
                        f"  Stopping at page {self.max_pages} (--max-pages limit)"
                    )
                    break

                page_url = f"{base_url}/{page}"

                logger.info(f"  Fetching page {page}...")
                response = await self.client.client.get(page_url)  # type: ignore[union-attr]

                if response.status_code != 200:
                    if page == 1:
                        logger.error(
                            f"Failed to fetch first page: {response.status_code}"
                        )
                    break

                # Parse editions from page (using actual HTML structure)
                soup = BeautifulSoup(response.text, "html.parser")

                # Find all article elements (same as collect_historical_pdfs.py)
                articles = soup.find_all(
                    "article", class_="list-item universal-list-item"
                )

                if not articles:
                    logger.debug(f"No more editions found on page {page}")
                    break

                logger.debug(f"  Found {len(articles)} edition(s) on page {page}")

                # Extract edition details URLs
                for article in articles:
                    try:
                        # Extract details URL from header section
                        header = article.find("header")
                        if not header:
                            continue

                        h2 = header.find("h2")
                        if not h2:
                            continue

                        link = h2.find("a", href=True)
                        if not link:
                            continue

                        details_url = str(link["href"])
                        if not details_url.startswith("http"):
                            details_url = self.client.base_url + details_url

                        # Fetch full edition details (includes download URL)
                        edition = await self.client._fetch_edition_details(details_url)
                        if not edition:
                            continue

                        # Use publication_date as key for matching
                        # publication_date is already a string in YYYY-MM-DD format
                        pub_date = edition.publication_date
                        editions_by_date[pub_date] = edition
                        logger.debug(f"    {pub_date}: {edition.title}")

                    except Exception as e:
                        logger.debug(f"Could not parse article: {e}")
                        continue

                    # Rate limiting
                    await asyncio.sleep(0.5)

                # Check for next page
                pagination = soup.find(class_="pagination")
                has_next_page = False
                if pagination:
                    next_item = pagination.find("li", class_="next")
                    has_next_page = next_item is not None

                if not has_next_page:
                    break

                page += 1
                await asyncio.sleep(1.0)  # Rate limiting between pages

            logger.info(f"✓ Found {len(editions_by_date)} editions on website")
            return editions_by_date

        except Exception as e:
            logger.error(f"Failed to discover editions: {e}")
            return {}

    def _parse_issue_from_title(self, title: str) -> tuple[int | None, int | None]:
        """Parse issue number and year from edition title.

        Examples:
            "Die 800% Strategie 04/2024" -> (4, 2024)
            "Megatrend Folger 52/2025" -> (52, 2025)

        Returns:
            Tuple of (issue_number, issue_year) or (None, None) if parsing fails
        """
        import re

        # Look for pattern: NN/YYYY (issue/year)
        match = re.search(r"(\d{1,2})/(\d{4})", title)
        if not match:
            return (None, None)

        issue_num = int(match.group(1))
        issue_year = int(match.group(2))
        return (issue_num, issue_year)

    async def _get_mongodb_entries(self, publication_id: str) -> list[dict]:
        """Get all MongoDB entries for a publication."""
        if not self.mongodb:
            raise RuntimeError("MongoDB not initialized")

        cursor = self.mongodb.db["processed_editions"].find(
            {"publication_id": publication_id},
            {
                "_id": 0,
                "edition_key": 1,
                "publication_id": 1,
                "publication_date": 1,
                "download_url": 1,
            },
        )

        results: list[dict[Any, Any]] = await cursor.to_list(None)
        return results

    async def _update_download_url(
        self, edition_key: str, download_url: str, onedrive_path: str | None = None
    ) -> None:
        """
        Update download_url for existing MongoDB entry and blob metadata.

        Args:
            edition_key: Edition key (e.g., "2025-12-18_megatrend-folger_51-2025")
            download_url: Web URL for downloading PDF
            onedrive_path: OneDrive path (if available, for blob lookup)
        """
        if not self.mongodb:
            raise RuntimeError("MongoDB not initialized")

        # Update MongoDB
        result = await self.mongodb.db["processed_editions"].update_one(
            {"edition_key": edition_key},
            {
                "$set": {
                    "download_url": download_url,
                    "web_sync_at": datetime.now(UTC).isoformat(),
                }
            },
        )

        if result.modified_count == 0:
            logger.warning(f"Failed to update MongoDB: {edition_key}")
            return

        # Update blob metadata (if blob storage available and path known)
        if self.blob_storage and onedrive_path:
            try:
                # Extract components from edition_key
                # Format: YYYY-MM-DD_publication-id_issue-year
                parts = edition_key.split("_")
                if len(parts) >= 3:
                    publication_date = parts[0]  # YYYY-MM-DD
                    publication_id = parts[1]  # e.g., "megatrend-folger"

                    # Extract filename from OneDrive path
                    # Example: "DepotButler/Megatrend Folger/2025/2025-12-18_Megatrend-Folger_51-2025.pdf"
                    filename = onedrive_path.split("/")[-1] if onedrive_path else None

                    if filename and publication_date and publication_id:
                        # Check if blob already has download_url
                        blob_client = (
                            self.blob_storage.container_client.get_blob_client(
                                self.blob_storage._generate_blob_path(
                                    publication_id, publication_date, filename
                                )
                            )
                        )

                        if blob_client.exists():
                            properties = blob_client.get_blob_properties()
                            existing_metadata = properties.metadata or {}
                            existing_url = existing_metadata.get("download_url", "")

                            # Only update if download_url is missing, empty, or null
                            if not existing_url or existing_url.strip() == "":
                                success = await self.blob_storage.update_metadata(
                                    publication_id=publication_id,
                                    date=publication_date,
                                    filename=filename,
                                    metadata={
                                        "download_url": download_url,
                                        "web_sync_at": datetime.now(UTC).isoformat(),
                                    },
                                )

                                if success:
                                    logger.debug(f"✓ Updated blob metadata: {filename}")
                                else:
                                    logger.debug(f"⚠ Blob not found: {filename}")
                            else:
                                logger.debug(f"⊘ Blob already has URL: {filename}")
                        else:
                            logger.debug(f"⚠ Blob not found: {filename}")
            except Exception as e:
                logger.warning(f"Failed to update blob metadata: {e}")
                # Don't fail the whole operation if blob update fails

    def _print_summary(self) -> None:
        """Print sync summary."""
        logger.info("=" * 70)
        logger.info("SYNC SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Web editions discovered:     {self.stats['web_discovered']}")
        logger.info(f"MongoDB entries:             {self.stats['mongodb_entries']}")
        logger.info(f"Matched (by date):           {self.stats['matched']}")
        logger.info(f"Updated with download_url:   {self.stats['updated']}")
        logger.info(f"Unmatched (web only):        {self.stats['unmatched_web']}")
        logger.info(f"Unmatched (MongoDB only):    {self.stats['unmatched_mongodb']}")
        logger.info(f"Failures:                    {self.stats['failed']}")
        logger.info("=" * 70)

        if self.dry_run:
            logger.info("")
            logger.info("🔍 This was a DRY-RUN. No changes were made.")
            logger.info("   Run without --dry-run to apply updates.")


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Sync web download URLs to MongoDB")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover and match only, don't update MongoDB",
    )
    parser.add_argument(
        "--publication",
        type=str,
        help="Sync specific publication (e.g., megatrend-folger)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        help="Limit pagination to N pages (for testing, default: all pages)",
    )

    args = parser.parse_args()

    # Configure logging with UTF-8 file handler
    log_level = logging.INFO  # Always use INFO level (DEBUG is too verbose)
    log_file = "data/tmp/sync_web_urls.log"

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Console handler (may have encoding issues on Windows)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # File handler with UTF-8 encoding (no encoding issues)
    file_handler = logging.FileHandler(log_file, encoding="utf-8", mode="w")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        handlers=[console_handler, file_handler],
    )

    logger.info(f"📝 Logging to: {log_file}")

    # Run sync
    async with WebUrlSync(
        dry_run=args.dry_run,
        publication_id=args.publication,
        max_pages=args.max_pages,
    ) as sync:
        await sync.sync_all_publications()


if __name__ == "__main__":
    asyncio.run(main())
