"""Publication processing service."""

import os
from pathlib import Path

from depotbutler.httpx_client import HttpxBoersenmedienClient
from depotbutler.mailer import EmailService
from depotbutler.models import (
    Edition,
    PublicationConfig,
    PublicationResult,
    UploadResult,
)
from depotbutler.onedrive import OneDriveService
from depotbutler.services.edition_tracking_service import EditionTrackingService
from depotbutler.settings import Settings
from depotbutler.utils.helpers import create_filename
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


class PublicationProcessingService:
    """Service for processing individual publications."""

    def __init__(
        self,
        boersenmedien_client: HttpxBoersenmedienClient,
        onedrive_service: OneDriveService,
        email_service: EmailService,
        edition_tracker: EditionTrackingService,
        settings: Settings,
        dry_run: bool = False,
    ):
        """
        Initialize publication processor.

        Args:
            boersenmedien_client: HTTP client for Börsenmedien
            onedrive_service: OneDrive service
            email_service: Email service
            edition_tracker: Edition tracking service
            settings: Application settings
            dry_run: If True, log actions without side effects
        """
        self.boersenmedien_client = boersenmedien_client
        self.onedrive_service = onedrive_service
        self.email_service = email_service
        self.edition_tracker = edition_tracker
        self.settings = settings
        self.dry_run = dry_run
        self.current_publication_data: dict | None = None

    async def process_publication(self, publication_data: dict) -> PublicationResult:
        """
        Process a single publication: check for new editions, download, email, upload.

        Args:
            publication_data: Publication document from MongoDB

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

            # Mark success and cleanup
            await self._finalize_processing(edition, str(download_path), pub_name)
            result.success = True

        except Exception as e:
            await self._handle_processing_error(e, pub_name, result)

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

        # OneDrive delivery
        if publication_data.get("onedrive_enabled", True):
            upload_result = await self._upload_to_onedrive(edition, download_path)
            result.upload_result = upload_result

            if not upload_result.success:
                result.error = f"OneDrive upload failed: {upload_result.error}"
                return False

            result.recipients_uploaded = 1
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
        await self.edition_tracker.mark_as_processed(edition, download_path)
        logger.info("   ✅ Marked as processed")

        await self._cleanup_files(download_path)
        logger.info(f"   ✅ {pub_name} completed successfully")

    async def _handle_processing_error(
        self, error: Exception, pub_name: str, result: PublicationResult
    ) -> None:
        """Handle errors during publication processing."""
        error_msg = f"Processing failed: {str(error)}"
        logger.error(f"   ❌ {pub_name}: {error_msg}")
        result.error = error_msg

        # Cleanup on error if we have a file
        if result.download_path:
            try:
                await self._cleanup_files(result.download_path)
            except Exception as cleanup_error:
                logger.error(f"   Cleanup failed: {cleanup_error}")

    async def _download_edition(self, edition: Edition) -> str | None:
        """
        Download a specific edition.

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

            # Download the PDF
            await self.boersenmedien_client.download_edition(edition, str(temp_path))

            return str(temp_path)

        except Exception as e:
            logger.error("Download failed: %s", e)
            return None

    async def _upload_to_onedrive(
        self, edition: Edition, local_path: str
    ) -> UploadResult:
        """
        Upload file to OneDrive using publication-specific folder.

        Args:
            edition: Edition being uploaded
            local_path: Local file path

        Returns:
            UploadResult with success status and file URL
        """
        try:
            # Authenticate with OneDrive
            auth_success = await self.onedrive_service.authenticate()
            if not auth_success:
                return UploadResult(
                    success=False, error="OneDrive authentication failed"
                )

            # Get publication-specific OneDrive folder and organization preference
            assert self.current_publication_data is not None
            folder_name = self.current_publication_data.get("default_onedrive_folder")
            organize_by_year = self.current_publication_data.get(
                "organize_by_year", True
            )

            if self.dry_run:
                logger.info(
                    "🧪 DRY-RUN: Would upload to OneDrive folder='%s', organize_by_year=%s",
                    folder_name,
                    organize_by_year,
                )
                # In dry-run mode, still query recipients to show what would happen
                from depotbutler.db.mongodb import get_mongodb_service

                mongodb = await get_mongodb_service()
                publication_id = self.current_publication_data.get("publication_id")
                assert publication_id is not None
                recipients = await mongodb.get_recipients_for_publication(
                    publication_id=publication_id, delivery_method="upload"
                )
                for recipient in recipients:
                    resolved_folder = mongodb.get_onedrive_folder_for_recipient(
                        recipient, self.current_publication_data
                    )
                    resolved_organize = mongodb.get_organize_by_year_for_recipient(
                        recipient, self.current_publication_data
                    )
                    logger.info(
                        "🧪 DRY-RUN: Would upload for %s to folder='%s', organize_by_year=%s",
                        recipient["email"],
                        resolved_folder,
                        resolved_organize,
                    )
                return UploadResult(success=True, file_url="dry-run-mode")

            # Upload file to OneDrive with publication's settings
            upload_result = await self.onedrive_service.upload_file(
                local_file_path=local_path,
                edition=edition,
                folder_name=folder_name,
                organize_by_year=organize_by_year,
            )

            return upload_result

        except Exception as e:
            logger.error("OneDrive upload error: %s", e)
            return UploadResult(success=False, error=str(e))

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
