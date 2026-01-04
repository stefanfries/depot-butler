"""
Historical PDF Collection Script

Downloads and archives all historical PDFs from boersenmedien.com to Azure Blob Storage.
This is a one-time backfill operation to populate the archive with past editions.

Usage:
    # Dry-run (discover only, no downloads)
    uv run python scripts/collect_historical_pdfs.py --dry-run

    # Test with specific publication and date range
    uv run python scripts/collect_historical_pdfs.py --publication megatrend-folger --start-date 2024-01-01 --end-date 2024-12-31 --dry-run

    # Full backfill (all publications, all time)
    uv run python scripts/collect_historical_pdfs.py

    # Resume from last checkpoint
    uv run python scripts/collect_historical_pdfs.py --resume

Features:
    - Discovers all available editions from website
    - Checks blob storage to skip already-archived editions
    - Downloads missing PDFs and archives to blob storage
    - Updates MongoDB with edition metadata
    - Progress reporting with checkpoint/resume capability
    - Dry-run mode for testing
    - Date range and publication filtering
    - Parallel downloads with rate limiting

Requirements:
    - Valid authentication cookie in MongoDB
    - Azure Storage connection configured
    - Sufficient disk space for temporary PDF storage
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from depotbutler.db.mongodb import MongoDBService, get_mongodb_service
from depotbutler.exceptions import EditionNotFoundError
from depotbutler.httpx_client import HttpxBoersenmedienClient
from depotbutler.models import Edition, PublicationConfig
from depotbutler.services.blob_storage_service import BlobStorageService
from depotbutler.settings import Settings
from depotbutler.utils.helpers import create_filename
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)
settings = Settings()


class HistoricalCollector:
    """Collects and archives historical PDFs."""

    def __init__(
        self,
        dry_run: bool = False,
        start_date: date | None = None,
        end_date: date | None = None,
        publication_id: str | None = None,
        checkpoint_file: Path | None = None,
    ) -> None:
        self.dry_run = dry_run
        self.start_date = start_date
        self.end_date = end_date
        self.publication_id = publication_id
        self.checkpoint_file = checkpoint_file or Path(
            "data/tmp/collection_checkpoint.json"
        )

        self.client: HttpxBoersenmedienClient | None = None
        self.blob_service: BlobStorageService | None = None
        self.mongodb: MongoDBService | None = None

        # Statistics
        self.stats = {
            "discovered": 0,
            "already_archived": 0,
            "downloaded": 0,
            "failed": 0,
            "skipped": 0,
        }

    async def __aenter__(self) -> HistoricalCollector:
        """Initialize services."""
        logger.info("Initializing historical collection...")

        # MongoDB
        self.mongodb = await get_mongodb_service()

        # HTTP Client
        self.client = HttpxBoersenmedienClient()
        await self.client.login()

        # Discover subscriptions (required for finding editions)
        await self.client.discover_subscriptions()
        logger.info(f"✓ Discovered {len(self.client.subscriptions)} subscription(s)")

        # Blob Storage (required for this script)
        if not settings.blob_storage.is_configured():
            raise RuntimeError(
                "Azure Blob Storage not configured. "
                "Please set AZURE_STORAGE_CONNECTION_STRING environment variable."
            )

        self.blob_service = BlobStorageService(
            container_name=settings.blob_storage.container_name,
        )

        return self

    async def __aexit__(
        self, exc_type: object, exc_val: object, exc_tb: object
    ) -> None:
        """Cleanup resources."""
        if self.client and self.client.client:
            await self.client.client.aclose()
        # BlobStorageService doesn't need async cleanup

    async def collect_all(self) -> None:
        """Main collection workflow."""
        logger.info("=" * 70)
        logger.info("HISTORICAL PDF COLLECTION")
        logger.info("=" * 70)

        if self.dry_run:
            logger.info("🔍 DRY-RUN MODE: No downloads will be performed")

        # Get publications to process
        publications = await self._get_publications()
        logger.info(f"Processing {len(publications)} publication(s)")

        # Load checkpoint if resuming
        checkpoint = self._load_checkpoint()

        # Process each publication
        for pub in publications:
            logger.info("")
            logger.info(f"{'=' * 70}")
            logger.info(f"Publication: {pub.name} (ID: {pub.id})")
            logger.info(f"{'=' * 70}")

            try:
                await self._process_publication(pub, checkpoint)
            except Exception as e:
                logger.error(
                    f"Failed to process publication {pub.name}: {e}", exc_info=True
                )
                self.stats["failed"] += 1

        # Final summary
        self._print_summary()

        # Cleanup checkpoint if fully successful
        if self.stats["failed"] == 0 and self.checkpoint_file.exists():
            self.checkpoint_file.unlink()
            logger.info("✓ Collection complete - checkpoint file removed")

    async def _get_publications(self) -> list[PublicationConfig]:
        """Get publications to process."""
        if not self.mongodb:
            raise RuntimeError("MongoDB not initialized")

        # If specific publication requested, get only that one
        if self.publication_id:
            pub_dict = await self.mongodb.get_publication(self.publication_id)
            if not pub_dict:
                raise ValueError(f"Publication not found: {self.publication_id}")
            # Convert MongoDB dict to PublicationConfig
            return [self._dict_to_publication_config(pub_dict)]

        # Otherwise get all active publications
        pubs_dicts = await self.mongodb.get_publications(active_only=True)
        # Convert MongoDB dicts to PublicationConfig objects
        return [self._dict_to_publication_config(pub) for pub in pubs_dicts]

    def _dict_to_publication_config(self, pub_dict: dict) -> PublicationConfig:
        """Convert MongoDB dict to PublicationConfig."""
        return PublicationConfig(
            id=pub_dict["publication_id"],
            name=pub_dict["name"],
            onedrive_folder=pub_dict.get("onedrive_folder", ""),
            recipients=pub_dict.get("recipients"),
            subscription_number=pub_dict.get("subscription_number"),
            subscription_id=pub_dict.get("subscription_id"),
        )

    async def _process_publication(
        self,
        publication: PublicationConfig,
        checkpoint: dict[str, Any],
    ) -> None:
        """Process all editions for a publication."""
        if not self.client or not self.blob_service or not self.mongodb:
            raise RuntimeError("Services not initialized")

        # Discover all available editions
        logger.info("Discovering available editions...")
        editions = await self._discover_all_editions(publication)

        if not editions:
            logger.warning(f"No editions found for {publication.name}")
            return

        self.stats["discovered"] += len(editions)
        logger.info(f"✓ Discovered {len(editions)} edition(s)")

        # Filter by date range if specified
        if self.start_date or self.end_date:
            editions = self._filter_by_date_range(editions)
            logger.info(f"✓ After date filtering: {len(editions)} edition(s)")

        # Check which editions are already archived
        logger.info("Checking blob storage for existing archives...")
        to_download = await self._filter_already_archived(publication, editions)

        already_archived = len(editions) - len(to_download)
        self.stats["already_archived"] += already_archived
        logger.info(f"✓ Already archived: {already_archived}")
        logger.info(f"✓ To download: {len(to_download)}")

        # Create list of editions that need MongoDB tracking
        # This includes both new downloads AND already-archived editions without MongoDB entries
        editions_to_track = []
        for edition in editions:
            edition_key = f"{edition.publication_date}_{publication.id}"
            # Check if already in MongoDB
            existing = await self.mongodb.get_edition(edition_key)
            if not existing:
                editions_to_track.append(edition)

        logger.info(f"✓ MongoDB entries to create: {len(editions_to_track)}")

        if not to_download and not editions_to_track:
            logger.info("All editions already archived and tracked - skipping")
            return

        # Process editions (download + archive)
        if to_download:
            logger.info("")
            logger.info("Downloading and archiving new editions...")

            for i, edition in enumerate(to_download, 1):
                # Check checkpoint - skip if already processed
                checkpoint_key = f"{publication.id}:{edition.title}"
                if checkpoint.get(checkpoint_key):
                    logger.info(
                        f"[{i}/{len(to_download)}] Skipping {edition.title} (checkpoint)"
                    )
                    self.stats["skipped"] += 1
                    continue

                logger.info(f"[{i}/{len(to_download)}] Processing: {edition.title}")

                try:
                    await self._process_edition(
                        publication, edition, needs_download=True
                    )
                    self.stats["downloaded"] += 1

                    # Update checkpoint
                    checkpoint[checkpoint_key] = {
                        "processed_at": datetime.now(UTC).isoformat(),
                        "title": edition.title,
                    }
                    self._save_checkpoint(checkpoint)

                except Exception as e:
                    logger.error(f"Failed to process {edition.title}: {e}")
                    self.stats["failed"] += 1

                # Rate limiting - be nice to the server
                await asyncio.sleep(2.0)

        # Track already-archived editions in MongoDB
        if editions_to_track:
            logger.info("")
            logger.info("Creating MongoDB entries for archived editions...")

            for i, edition in enumerate(editions_to_track, 1):
                # Skip if this edition was just downloaded (already tracked)
                if edition in to_download:
                    continue

                logger.info(f"[{i}/{len(editions_to_track)}] Tracking: {edition.title}")

                try:
                    await self._process_edition(
                        publication, edition, needs_download=False
                    )
                except Exception as e:
                    logger.error(f"Failed to track {edition.title}: {e}")
                    self.stats["failed"] += 1

    async def _discover_all_editions(
        self,
        publication: PublicationConfig,
    ) -> list[Edition]:
        """Discover all available editions for a publication with pagination support."""
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
                return []

            all_editions: list[Edition] = []
            page = 1

            # Get base URL (everything up to and including /ausgaben)
            base_url = subscription.content_url
            if base_url.endswith("/ausgaben/1"):
                base_url = base_url[:-2]  # Remove the "/1"
            elif not base_url.endswith("/ausgaben") and "/ausgaben/" in base_url:
                # If URL doesn't end with /ausgaben, find it and trim
                base_url = base_url.split("/ausgaben")[0] + "/ausgaben"

            # Paginate through all pages
            while True:
                # Build page URL: /ausgaben/1, /ausgaben/2, etc.
                page_url = f"{base_url}/{page}"

                logger.info(f"Fetching page {page}...")
                page_start = time.time()
                response = await self.client.client.get(page_url)  # type: ignore[union-attr]
                page_time = (time.time() - page_start) * 1000

                if response.status_code != 200:
                    logger.error(f"Failed to fetch page {page}: {response.status_code}")
                    break

                # Parse edition articles from this page
                soup = BeautifulSoup(response.text, "html.parser")

                # Find all article elements (30 per page)
                articles = soup.find_all(
                    "article", class_="list-item universal-list-item"
                )

                if not articles:
                    logger.info(f"No more editions found on page {page}")
                    break

                logger.info(
                    f"Found {len(articles)} edition(s) on page {page} ({page_time:.0f}ms)"
                )

                # Collect edition URLs from article headers
                edition_urls = []
                duplicates_found = 0
                for article in articles:
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

                    # Avoid duplicates (pagination might overlap)
                    if details_url not in [e.details_url for e in all_editions]:
                        edition_urls.append(details_url)
                    else:
                        duplicates_found += 1

                if duplicates_found > 0:
                    logger.info(
                        f"  Skipped {duplicates_found} duplicate URL(s) on page {page}"
                    )

                # Check for next page: look for <li class="next"> in pagination
                pagination = soup.find(class_="pagination")
                has_next_page = False
                if pagination:
                    next_item = pagination.find("li", class_="next")
                    has_next_page = next_item is not None

                # Fetch details for editions on this page
                editions_on_page = 0
                for details_url in edition_urls:
                    try:
                        detail_start = time.time()
                        edition = await self.client._fetch_edition_details(details_url)
                        detail_time = (time.time() - detail_start) * 1000

                        if edition:
                            all_editions.append(edition)
                            editions_on_page += 1
                            filename = create_filename(edition)
                            logger.info(
                                f"  [{editions_on_page}/{len(edition_urls)}] {edition.publication_date} | "
                                f"{edition.title} | {filename} ({detail_time:.0f}ms)"
                            )
                    except Exception as e:
                        logger.warning(f"Failed to fetch edition {details_url}: {e}")
                        continue

                    # Small delay to avoid overwhelming server
                    await asyncio.sleep(0.5)

                # Stop if no next page link found
                if not has_next_page:
                    logger.info("No more pages available")
                    break

                page += 1

                # Safety limit: max 50 pages (30 editions/page = 1500 editions max)
                if page > 50:
                    logger.warning("Reached pagination safety limit (50 pages)")
                    break

                # Delay between pages
                await asyncio.sleep(1.0)

            logger.info(
                f"Total editions discovered across {page} page(s): {len(all_editions)}"
            )
            return all_editions

        except EditionNotFoundError:
            logger.warning(f"No editions found for {publication.name}")
            return []

    def _filter_by_date_range(self, editions: list[Edition]) -> list[Edition]:
        """Filter editions by date range."""
        filtered = []

        for edition in editions:
            if not edition.publication_date:
                # If no date, include it
                filtered.append(edition)
                continue

            # Convert publication_date string to date object for comparison
            edition_date = datetime.strptime(
                edition.publication_date, "%Y-%m-%d"
            ).date()

            if self.start_date and edition_date < self.start_date:
                continue

            if self.end_date and edition_date > self.end_date:
                continue

            filtered.append(edition)

        return filtered

    async def _filter_already_archived(
        self,
        publication: PublicationConfig,
        editions: list[Edition],
    ) -> list[Edition]:
        """Filter out editions that are already archived."""
        if not self.blob_service:
            raise RuntimeError("Blob service not initialized")

        to_download = []

        for i, edition in enumerate(editions, 1):
            # Generate expected filename
            filename = create_filename(edition)

            # Check if already in blob storage
            check_start = time.time()
            exists = await self.blob_service.exists(
                publication_id=publication.id,
                date=edition.publication_date,
                filename=filename,
            )
            check_time = (time.time() - check_start) * 1000

            status = "ARCHIVED" if exists else "MISSING"
            logger.info(
                f"  [{i}/{len(editions)}] {edition.publication_date} | "
                f"{edition.title} | {filename} | {status} ({check_time:.0f}ms)"
            )

            if not exists:
                to_download.append(edition)

        return to_download

    async def _process_edition(
        self,
        publication: PublicationConfig,
        edition: Edition,
        needs_download: bool = True,
    ) -> None:
        """Download and archive a single edition, or just create MongoDB entry for existing."""
        if self.dry_run:
            logger.info(f"  [DRY-RUN] Would download: {edition.title}")
            return

        if not self.client or not self.blob_service or not self.mongodb:
            raise RuntimeError("Services not initialized")

        # Generate filename
        filename = create_filename(edition)

        # Timestamps
        import_time = datetime.now(UTC)

        if needs_download:
            # Download PDF
            logger.info(f"  Downloading {edition.title}...")
            pdf_data = await self._download_pdf(edition.download_url)

            # Archive to blob storage
            logger.info("  Archiving to blob storage...")
            blob_metadata = await self.blob_service.archive_edition(
                pdf_bytes=pdf_data,
                publication_id=publication.id,
                filename=filename,
                date=edition.publication_date,
                metadata={
                    "title": edition.title.title(),
                    "publication_id": publication.id,
                    "source": "web_historical",
                    "download_url": edition.download_url,
                },
            )
            logger.info(f"  ✓ Archived: {blob_metadata['blob_url']}")
        else:
            # Already archived - get metadata from blob storage
            blob_path = self.blob_service._generate_blob_path(
                publication.id, edition.publication_date, filename
            )
            blob_client = self.blob_service.container_client.get_blob_client(blob_path)
            properties = blob_client.get_blob_properties()

            blob_metadata = {
                "blob_url": blob_client.url,
                "blob_path": blob_path,
                "blob_container": self.blob_service.container_name,
                "file_size_bytes": properties.size,
            }

        # Mark as processed in MongoDB with blob metadata (matches regular workflow)
        edition_key = f"{edition.publication_date}_{publication.id}"
        await self.mongodb.mark_edition_processed(
            edition_key=edition_key,
            publication_id=publication.id,
            title=edition.title,
            publication_date=edition.publication_date,
            download_url=edition.download_url,
            file_path="",  # OneDrive path will be filled by import script
            blob_url=blob_metadata["blob_url"],
            blob_path=blob_metadata["blob_path"],
            blob_container=blob_metadata["blob_container"],
            file_size_bytes=int(blob_metadata["file_size_bytes"]),
            downloaded_at=import_time,
            archived_at=import_time,
            source="web_historical",
        )

    async def _download_pdf(self, download_url: str) -> bytes:
        """Download PDF and return bytes."""
        if not self.client or not self.client.client:
            raise RuntimeError("Client not initialized")

        response = await self.client.client.get(download_url)
        response.raise_for_status()
        return bytes(response.content)

    def _load_checkpoint(self) -> dict[str, Any]:
        """Load checkpoint file if it exists."""
        if not self.checkpoint_file.exists():
            return {}

        try:
            with self.checkpoint_file.open() as f:
                checkpoint: dict[str, Any] = json.load(f)
                logger.info(
                    f"✓ Loaded checkpoint: {len(checkpoint)} editions processed"
                )
                return checkpoint
        except Exception as e:
            logger.warning(f"Could not load checkpoint: {e}")
            return {}

    def _save_checkpoint(self, checkpoint: dict[str, Any]) -> None:
        """Save checkpoint file."""
        try:
            self.checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
            with self.checkpoint_file.open("w") as f:
                json.dump(checkpoint, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save checkpoint: {e}")

    def _print_summary(self) -> None:
        """Print collection summary."""
        logger.info("")
        logger.info("=" * 70)
        logger.info("COLLECTION SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Discovered:        {self.stats['discovered']}")
        logger.info(f"Already archived:  {self.stats['already_archived']}")
        logger.info(f"Downloaded:        {self.stats['downloaded']}")
        logger.info(f"Skipped:           {self.stats['skipped']}")
        logger.info(f"Failed:            {self.stats['failed']}")
        logger.info("=" * 70)

        if self.stats["failed"] > 0:
            logger.warning("⚠️  Some editions failed - see logs above")
            logger.info("Run with --resume to retry failed editions")
        elif self.dry_run:
            logger.info("🔍 Dry-run complete - no changes made")
        else:
            logger.info("✓ Collection complete!")


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Collect and archive historical PDFs from boersenmedien.com"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover only, don't download or archive",
    )
    parser.add_argument(
        "--publication",
        type=str,
        help="Process specific publication ID only (e.g., megatrend-folger)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date in YYYY-MM-DD format (inclusive)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date in YYYY-MM-DD format (inclusive)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last checkpoint",
    )

    args = parser.parse_args()

    # Parse dates
    start_date = None
    end_date = None

    if args.start_date:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()

    if args.end_date:
        end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date()

    # Setup file logging with UTF-8 encoding for ALL loggers
    log_dir = Path("data/tmp")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "historical_pdf_collection.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    # Add to root logger to capture all module logs
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.INFO)

    # Reduce verbosity of Azure SDK logging (too detailed)
    logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
        logging.WARNING
    )
    logging.getLogger("azure").setLevel(logging.WARNING)

    logger.info(f"Logging to {log_file}")

    # Run collector
    async with HistoricalCollector(
        dry_run=args.dry_run,
        start_date=start_date,
        end_date=end_date,
        publication_id=args.publication,
    ) as collector:
        await collector.collect_all()


if __name__ == "__main__":
    asyncio.run(main())
