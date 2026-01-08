from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from depotbutler.httpx_client import HttpxBoersenmedienClient
from depotbutler.mailer import EmailService
from depotbutler.models import (
    Edition,
    PublicationConfig,
    PublicationResult,
    UploadResult,
)
from depotbutler.observability import MetricsTracker
from depotbutler.onedrive import OneDriveService
from depotbutler.services.edition_tracking_service import EditionTrackingService
from depotbutler.services.onedrive_delivery_service import OneDriveDeliveryService
from depotbutler.settings import Settings
from depotbutler.utils.helpers import create_filename
from depotbutler.utils.logger import get_logger

if TYPE_CHECKING:
    from depotbutler.services.blob_storage_service import BlobStorageService

logger = get_logger(__name__)


class PublicationProcessingService:
    """Service for processing individual publications."""

    def __init__(
        self,
        boersenmedien_client: HttpxBoersenmedienClient,
        onedrive_service: OneDriveService,
        email_service: EmailService,
        edition_tracker: EditionTrackingService,
        blob_service: BlobStorageService | None,
        settings: Settings,
        dry_run: bool = False,
        use_cache: bool = False,
    ) -> None:
        """
        Initialize publication processor.

        Args:
            boersenmedien_client: HTTP client for Börsenmedien
            onedrive_service: OneDrive service
            email_service: Email service
            edition_tracker: Edition tracking service
            blob_service: Optional blob storage service for archival
            settings: Application settings
            dry_run: If True, log actions without side effects
            use_cache: If True, check blob storage cache before downloading
        """
        self.boersenmedien_client = boersenmedien_client
        self.onedrive_service = onedrive_service
        self.email_service = email_service
        self.edition_tracker = edition_tracker
        self.blob_service = blob_service
        self.settings = settings
        self.dry_run = dry_run
        self.use_cache = use_cache
        self.current_publication_data: dict | None = None
        self.delivery_service = OneDriveDeliveryService(
            onedrive_service, edition_tracker, dry_run
        )

    async def process_publication(
        self, publication_data: dict, metrics_tracker: MetricsTracker | None = None
    ) -> PublicationResult:
        """
        Process a single publication: check for new editions, download, email, upload.

        Args:
            publication_data: Publication document from MongoDB
            metrics_tracker: Optional metrics tracker to record errors

        Returns:
            PublicationResult with processing status and details
        """
        pub_id = publication_data["publication_id"]
        pub_name = publication_data["name"]

        logger.info(f"📰 Processing publication: {pub_name}")
        logger.info(
            f"   Email: {publication_data.get('email_enabled', True)} | "
            f"OneDrive: {publication_data.get('onedrive_enabled', True)}"
        )

        result = PublicationResult(
            publication_id=pub_id,
            publication_name=pub_name,
            success=False,
        )

        try:
            # Get and check edition
            edition = await self._get_and_check_edition(
                publication_data, pub_id, pub_name, result
            )
            if not edition:
                return result

            # Check if already processed
            if await self.edition_tracker.is_already_processed(edition):
                logger.info("   ✅ Already processed, skipping")
                result.already_processed = True
                result.success = True
                return result

            logger.info("   📥 New edition - processing...")

            # Download and deliver
            download_path = await self._download_edition(edition)
            if not download_path:
                result.error = "Failed to download edition"
                return result

            result.download_path = download_path

            # Deliver via email and OneDrive
            delivery_success = await self._deliver_edition(
                publication_data, edition, str(download_path), result
            )
            if not delivery_success:
                return result

            # Archive to blob storage (non-blocking - don't fail workflow if this fails)
            # Pass OneDrive file_path from delivery result for blob metadata
            blob_metadata = await self._archive_to_blob_storage(
                edition,
                str(download_path),
                onedrive_file_path=result.upload_result.onedrive_file_path
                if result.upload_result
                else None,
            )

            # Store archival info in result
            if blob_metadata:
                result.archived = True
                result.blob_url = blob_metadata.get("blob_url")
                result.archived_at = datetime.now(UTC)
            else:
                result.archived = False

            # Update publication delivery statistics
            await self._update_publication_statistics(pub_id)

            # Mark success and cleanup
            await self._finalize_processing(edition, str(download_path), pub_name)
            result.success = True

        except Exception as e:
            await self._handle_processing_error(e, pub_name, result, metrics_tracker)

        return result

    async def _get_and_check_edition(
        self,
        publication_data: dict,
        pub_id: str,
        pub_name: str,
        result: PublicationResult,
    ) -> Edition | None:
        """Get latest edition info and check if available."""
        self.current_publication_data = publication_data

        publication = PublicationConfig(
            id=pub_id,
            name=pub_name,
            onedrive_folder=publication_data.get("default_onedrive_folder", ""),
            subscription_number=publication_data.get("subscription_number"),
            subscription_id=publication_data.get("subscription_id"),
        )

        edition = await self.boersenmedien_client.get_latest_edition(publication)
        if not edition:
            result.error = "Failed to get latest edition"
            return None

        edition = await self.boersenmedien_client.get_publication_date(edition)
        result.edition = edition

        logger.info(f"   Found: {edition.title} ({edition.publication_date})")
        return edition

    async def _deliver_edition(
        self,
        publication_data: dict,
        edition: Edition,
        download_path: str,
        result: PublicationResult,
    ) -> bool:
        """
        Deliver edition via email and/or OneDrive based on settings.

        Returns:
            True if delivery succeeded, False on error
        """
        # Email delivery
        if publication_data.get("email_enabled", True):
            email_success = await self._send_pdf_email(edition, download_path)
            result.email_result = email_success
            if email_success:
                result.recipients_emailed = 1
        else:
            logger.info("   📧 Email disabled, skipping")
            result.email_result = None

        # OneDrive delivery (per-recipient uploads)
        if publication_data.get("onedrive_enabled", True):
            assert self.current_publication_data is not None
            upload_result = await self.delivery_service.upload_for_recipients(
                edition, download_path, self.current_publication_data
            )
            result.upload_result = upload_result

            if not upload_result.success:
                result.error = f"OneDrive upload failed: {upload_result.error}"
                return False

            # Extract recipient count from file_url (format: "N recipient(s)")
            if upload_result.file_url and "recipient" in upload_result.file_url:
                try:
                    result.recipients_uploaded = int(upload_result.file_url.split()[0])
                except (ValueError, IndexError):
                    result.recipients_uploaded = 1
            else:
                result.recipients_uploaded = 0

            # Update file_path in MongoDB (tracks OneDrive location)
            await self.delivery_service.update_file_path_in_mongodb(
                edition, upload_result.onedrive_file_path
            )
        else:
            logger.info("   ☁️ OneDrive disabled, skipping")
            result.upload_result = UploadResult(
                success=True,
                file_url="N/A (OneDrive disabled)",
                file_id="N/A",
            )

        return True

    async def _finalize_processing(
        self, edition: Edition, download_path: str, pub_name: str
    ) -> None:
        """Mark edition as processed, cleanup files, and log completion."""
        if not self.dry_run:
            assert self.current_publication_data is not None
            await self.edition_tracker.mark_as_processed(
                edition, self.current_publication_data["publication_id"], download_path
            )
            logger.info("   ✅ Marked as processed")
        else:
            logger.info("   🧪 DRY-RUN: Skipped marking as processed")

        await self._cleanup_files(download_path)
        logger.info(f"   ✅ {pub_name} completed successfully")

    async def _handle_processing_error(
        self,
        error: Exception,
        pub_name: str,
        result: PublicationResult,
        metrics_tracker: MetricsTracker | None = None,
    ) -> None:
        """Handle errors during publication processing."""
        error_msg = f"Processing failed: {str(error)}"
        logger.error(f"   ❌ {pub_name}: {error_msg}")
        result.error = error_msg

        # Record error in metrics tracker if available
        if metrics_tracker:
            metrics_tracker.record_error(
                error,
                operation="process_publication",
                context={
                    "publication": pub_name,
                    "publication_id": result.publication_id,
                },
            )

        # Cleanup on error if we have a file
        if result.download_path:
            try:
                await self._cleanup_files(result.download_path)
            except Exception as cleanup_error:
                logger.error(f"   Cleanup failed: {cleanup_error}")

    async def _download_edition(self, edition: Edition) -> str | None:
        """
        Download a specific edition.

        If use_cache is enabled and blob storage is configured, checks cache first.
        Falls back to downloading from website if not in cache.

        Args:
            edition: Edition to download

        Returns:
            Path to downloaded file, or None on failure
        """
        try:
            # Generate local filename using helper
            filename = create_filename(edition)

            # Store temporary files in dedicated temp directory
            temp_dir = Path(self.settings.tracking.temp_dir)
            temp_path = temp_dir / filename

            # Ensure the tmp directory exists
            temp_dir.mkdir(parents=True, exist_ok=True)

            # Check blob storage cache if enabled
            if self.use_cache and self.blob_service:
                assert self.current_publication_data is not None
                publication_id = self.current_publication_data.get("publication_id")
                assert publication_id is not None

                logger.info("   📦 Checking blob storage cache...")
                cached_pdf = await self.blob_service.get_cached_edition(
                    publication_id=publication_id,
                    date=edition.publication_date,
                    filename=filename,
                )

                if cached_pdf:
                    # Save cached PDF to temp file
                    with open(temp_path, "wb") as f:
                        f.write(cached_pdf)
                    logger.info("   ✓ Retrieved from cache (skipped download)")
                    return str(temp_path)
                else:
                    logger.info("   Cache miss - downloading from website")

            # Download the PDF
            download_start = datetime.now(UTC)
            await self.boersenmedien_client.download_edition(edition, str(temp_path))

            # Track download timestamp in MongoDB (skip in dry-run)
            if not self.dry_run:
                assert self.current_publication_data is not None
                edition_key = self.edition_tracker._generate_edition_key(edition)
                from depotbutler.db.mongodb import get_mongodb_service

                mongodb = await get_mongodb_service()
                # Initialize edition record if needed (with download timestamp)
                if mongodb.edition_repo:
                    await mongodb.edition_repo.mark_edition_processed(
                        edition_key=edition_key,
                        publication_id=self.current_publication_data["publication_id"],
                        title=edition.title.title(),
                        publication_date=edition.publication_date,
                        download_url=edition.download_url,
                        file_path="",  # OneDrive path will be filled by import script
                        downloaded_at=download_start,
                        source="scheduled_job",
                    )
                    logger.info("   ✓ Download timestamp recorded")
            else:
                logger.info("   🧪 DRY-RUN: Skipped download timestamp recording")

            return str(temp_path)

        except Exception as e:
            logger.error("Download failed: %s", e)
            return None

    async def _send_pdf_email(self, edition: Edition, pdf_path: str) -> bool:
        """
        Send PDF file via email to recipients subscribed to current publication.

        Args:
            edition: Edition being sent
            pdf_path: Path to PDF file

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get publication_id from current_publication_data if available
            publication_id = None
            if self.current_publication_data:
                publication_id = self.current_publication_data.get("publication_id")

            if self.dry_run:
                logger.info(
                    "🧪 DRY-RUN: Would send email to recipients for publication_id=%s",
                    publication_id,
                )
                # In dry-run mode, still query recipients to show what would happen
                from depotbutler.db.mongodb import get_mongodb_service

                mongodb = await get_mongodb_service()
                assert publication_id is not None
                recipients = await mongodb.get_recipients_for_publication(
                    publication_id=publication_id, delivery_method="email"
                )
                for recipient in recipients:
                    logger.info("🧪 DRY-RUN: Would send to %s", recipient["email"])
                return True

            success = await self.email_service.send_pdf_to_recipients(
                pdf_path=pdf_path, edition=edition, publication_id=publication_id
            )
            if success:
                logger.info("📧 PDF successfully sent via email to all recipients")

                # Track email sent timestamp (skip in dry-run - but this code path won't execute in dry-run anyway)
                if not self.dry_run:
                    edition_key = self.edition_tracker._generate_edition_key(edition)
                    from depotbutler.db.mongodb import get_mongodb_service

                    mongodb = await get_mongodb_service()
                    if mongodb.edition_repo:
                        await mongodb.edition_repo.update_email_sent_timestamp(
                            edition_key
                        )
                        logger.info("   ✓ Email sent timestamp recorded")
            else:
                logger.error("📧 Failed to send PDF via email to some/all recipients")
            return success

        except Exception as e:
            logger.error("Error sending PDF via email: %s", e)
            return False

    async def _cleanup_files(self, file_path: str) -> None:
        """
        Remove temporary downloaded files.

        Args:
            file_path: Path to file to remove
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info("Cleaned up temporary file: %s", file_path)
        except Exception as e:
            logger.warning("Failed to cleanup file %s: %s", file_path, e)

    async def _archive_to_blob_storage(
        self, edition: Edition, local_path: str, onedrive_file_path: str | None = None
    ) -> dict[str, Any] | None:
        """
        Archive edition PDF to Azure Blob Storage (non-blocking).

        This method is called after successful delivery. If archival fails,
        the workflow continues without raising an error.

        Args:
            edition: Edition being archived
            local_path: Local file path to PDF
            onedrive_file_path: OneDrive path where file is stored (optional)

        Returns:
            Blob metadata dict if successful, None if archival was skipped or failed
        """
        # Skip if blob storage not configured
        if not self.blob_service:
            logger.debug("Blob storage not configured, skipping archival")
            return None

        if self.dry_run:
            logger.info("🧪 DRY-RUN: Would archive to blob storage")
            return None

        try:
            # Read PDF file
            with open(local_path, "rb") as f:
                pdf_bytes = f.read()

            # Get publication ID for blob path
            assert self.current_publication_data is not None
            publication_id = self.current_publication_data.get("publication_id")
            assert publication_id is not None

            # Generate filename from edition
            filename = create_filename(edition)

            # If OneDrive path not provided, construct it from publication config
            if not onedrive_file_path:
                default_folder = self.current_publication_data.get(
                    "default_onedrive_folder", ""
                )
                year = edition.publication_date.split("-")[0]

                # Check organize_by_year setting
                from depotbutler.db.mongodb import get_mongodb_service

                mongodb = await get_mongodb_service()
                if "onedrive_organize_by_year" in self.current_publication_data:
                    organize_by_year = self.current_publication_data[
                        "onedrive_organize_by_year"
                    ]
                else:
                    organize_by_year = await mongodb.get_app_config(
                        "onedrive_organize_by_year", default=True
                    )

                if organize_by_year and default_folder:
                    onedrive_file_path = f"{default_folder}/{year}/{filename}"
                elif default_folder:
                    onedrive_file_path = f"{default_folder}/{filename}"

            # Archive to blob storage
            logger.info("   ☁️ Archiving to blob storage...")

            # Sanitize title for blob metadata (US ASCII only)
            from depotbutler.utils.helpers import sanitize_for_blob_metadata

            edition_title_ascii = sanitize_for_blob_metadata(edition.title.title())

            # Build metadata with OneDrive path and download URL if available
            metadata = {
                "title": edition_title_ascii,
                "publication_id": publication_id,
                "source": "scheduled_job",
            }
            if edition.download_url:
                metadata["download_url"] = edition.download_url
            if onedrive_file_path:
                metadata["onedrive_file_path"] = onedrive_file_path

            blob_metadata = await self.blob_service.archive_edition(
                pdf_bytes=pdf_bytes,
                publication_id=publication_id,
                date=edition.publication_date,
                filename=filename,
                metadata=metadata,
            )

            # Update MongoDB with blob metadata
            edition_key = self.edition_tracker._generate_edition_key(edition)
            from depotbutler.db.mongodb import get_mongodb_service

            mongodb = await get_mongodb_service()
            if mongodb.edition_repo:
                archived_at = datetime.now(UTC)
                await mongodb.edition_repo.update_blob_metadata(
                    edition_key=edition_key,
                    blob_url=blob_metadata["blob_url"],
                    blob_path=blob_metadata["blob_path"],
                    blob_container=blob_metadata["blob_container"],
                    file_size_bytes=int(blob_metadata["file_size_bytes"]),
                    archived_at=archived_at,
                )
                logger.info("   ✓ Blob metadata recorded in MongoDB")

            return blob_metadata

        except Exception as e:
            # Non-blocking: log error but don't fail workflow
            logger.warning(
                "Failed to archive to blob storage (continuing workflow): %s", e
            )
            return None

    async def _update_publication_statistics(self, publication_id: str) -> None:
        """
        Update publication delivery statistics after successful delivery.

        Increments delivery_count and updates last_delivered_at timestamp.

        Args:
            publication_id: ID of the publication that was delivered
        """
        if self.dry_run:
            logger.debug("🧪 DRY-RUN: Would update publication statistics")
            return

        try:
            from depotbutler.db.mongodb import get_mongodb_service

            mongodb = await get_mongodb_service()

            # Increment delivery count and update last delivered timestamp
            await mongodb.db.publications.update_one(
                {"publication_id": publication_id},
                {
                    "$inc": {"delivery_count": 1},
                    "$set": {"last_delivered_at": datetime.now(UTC)},
                },
            )

            logger.debug(f"Updated delivery statistics for {publication_id}")

        except Exception as e:
            # Non-blocking: log error but don't fail workflow
            logger.warning(
                f"Failed to update publication statistics (continuing workflow): {e}"
            )
