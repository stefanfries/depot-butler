"""
Main workflow orchestrator for DepotButler.
Coordinates downloading, uploading to OneDrive, and email notifications.
Includes edition tracking to prevent duplicate processing.
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Optional

from depotbutler.client import BoersenmedienClient
from depotbutler.db.mongodb import close_mongodb_connection
from depotbutler.edition_tracker import EditionTracker
from depotbutler.mailer import EmailService
from depotbutler.models import Edition, UploadResult
from depotbutler.onedrive import OneDriveService
from depotbutler.publications import PUBLICATIONS
from depotbutler.settings import Settings
from depotbutler.utils.helpers import create_filename
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


class DepotButlerWorkflow:
    """
    Main workflow orchestrator for automated PDF processing.

    Workflow:
    1. Check if edition was already processed (skip if yes)
    2. Login to boersenmedien.com and download latest edition
    3. Send PDF via email to recipients
    4. Upload PDF to OneDrive
    5. Send success notification to admin
    6. Mark edition as processed
    7. Cleanup temporary files
    """

    def __init__(self, tracking_file_path: Optional[str] = None):
        self.settings = Settings()
        self.boersenmedien_client: Optional[BoersenmedienClient] = None
        self.onedrive_service: Optional[OneDriveService] = None
        self.email_service: Optional[EmailService] = None

        # Initialize edition tracker
        if not self.settings.tracking.enabled:
            # If tracking is disabled, use a dummy tracker that never blocks
            class DummyTracker:
                def is_already_processed(self, edition):
                    return False

                def mark_as_processed(self, edition, file_path=""):
                    pass

                def get_processed_count(self):
                    return 0

                def get_recent_editions(self, days):
                    return []

                def force_reprocess(self, edition):
                    return False

            self.edition_tracker = DummyTracker()
            logger.info("Edition tracking is disabled")
        else:
            # Use provided path, settings path, or fallback
            if tracking_file_path:
                tracker_path = tracking_file_path
            else:
                tracker_path = self.settings.tracking.file_path

            try:
                self.edition_tracker = EditionTracker(
                    tracking_file_path=tracker_path,
                    retention_days=self.settings.tracking.retention_days,
                )
                logger.info("Edition tracking enabled with file: %s", tracker_path)
            except OSError:
                # Fallback for local development
                local_path = Path.cwd() / "data" / "processed_editions.json"
                self.edition_tracker = EditionTracker(
                    tracking_file_path=str(local_path),
                    retention_days=self.settings.tracking.retention_days,
                )
                logger.info("Using local tracking file: %s", local_path)

    async def __aenter__(self):
        """Async context manager entry."""
        self.boersenmedien_client = BoersenmedienClient()
        self.onedrive_service = OneDriveService()
        self.email_service = EmailService()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup."""
        if self.boersenmedien_client:
            await self.boersenmedien_client.close()
        if self.onedrive_service:
            await self.onedrive_service.close()
        # Close MongoDB connection
        await close_mongodb_connection()

    async def run_full_workflow(self) -> dict:
        """
        Execute the complete DepotButler workflow with edition tracking.

        Returns:
            Dict with workflow results and status information
        """
        workflow_start = perf_counter()

        workflow_result = {
            "success": False,
            "edition": None,
            "download_path": None,
            "upload_result": None,
            "already_processed": False,
            "error": None,
        }

        try:
            logger.info(
                "🚀 Starting DepotButler workflow [timestamp=%s]",
                datetime.now().isoformat(),
            )

            # Step 1: Get latest edition info (without downloading yet)
            logger.info("� Step 1: Checking for new editions")
            edition = await self._get_latest_edition_info()
            workflow_result["edition"] = edition

            if not edition:
                raise Exception("Failed to get latest edition information")

            # Step 2: Check if already processed
            if self.edition_tracker.is_already_processed(edition):
                logger.info(
                    f"✅ Edition already processed: {edition.title} ({edition.publication_date})"
                )
                workflow_result["already_processed"] = True
                workflow_result["success"] = True
                return workflow_result

            logger.info(
                f"📥 New edition found: {edition.title} ({edition.publication_date})"
            )

            # Step 3: Download the edition
            logger.info("📥 Step 3: Downloading new edition")
            download_path = await self._download_edition(edition)
            workflow_result["download_path"] = download_path

            if not download_path:
                raise Exception("Failed to download edition")

            # Step 4: Send PDF via email
            logger.info("📧 Step 4: Sending PDF via email")
            email_success = await self._send_pdf_email(edition, download_path)
            if not email_success:
                logger.warning("Email sending failed, but continuing with workflow")

            # Step 5: Upload to OneDrive
            logger.info("☁️ Step 5: Uploading to OneDrive")
            upload_result = await self._upload_to_onedrive(edition, download_path)
            workflow_result["upload_result"] = upload_result

            if not upload_result.success:
                raise Exception(f"OneDrive upload failed: {upload_result.error}")

            # Step 6: Mark as processed (do this before notifications to ensure it's recorded)
            self.edition_tracker.mark_as_processed(edition, download_path)
            logger.info("✅ Edition marked as processed")

            # Step 7: Send success notification
            logger.info("📧 Step 7: Sending success notification")
            await self._send_success_notification(edition, upload_result)

            # Step 8: Cleanup
            logger.info("🧹 Step 8: Cleaning up temporary files")
            await self._cleanup_files(download_path)

            workflow_result["success"] = True
            elapsed = perf_counter() - workflow_start
            logger.info(
                "✅ DepotButler workflow completed successfully [total_time=%.2fs]",
                elapsed,
            )

        except Exception as e:
            error_msg = f"Workflow failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            workflow_result["error"] = error_msg

            # Send error notification
            await self._send_error_notification(workflow_result["edition"], error_msg)

            # Still cleanup if we have a file
            if workflow_result["download_path"]:
                await self._cleanup_files(workflow_result["download_path"])

        return workflow_result

    async def _get_latest_edition_info(self) -> Optional[Edition]:
        """Get information about the latest edition without downloading."""
        try:
            # Login to boersenmedien.com
            await self.boersenmedien_client.login()

            # Discover subscriptions
            await self.boersenmedien_client.discover_subscriptions()

            # Use first configured publication (for now)
            if not PUBLICATIONS:
                logger.error("No publications configured in publications.py")
                return None

            publication = PUBLICATIONS[0]
            logger.info("Processing publication: %s", publication.name)

            # Get latest edition info
            edition = await self.boersenmedien_client.get_latest_edition(publication)
            logger.info("Found edition: %s", edition.title)

            # Get publication date
            edition = await self.boersenmedien_client.get_publication_date(edition)
            logger.info("Publication date: %s", edition.publication_date)

            return edition

        except Exception as e:
            logger.error("Failed to get edition info: %s", e)
            return None

    async def _download_edition(self, edition: Edition) -> Optional[str]:
        """Download a specific edition."""
        try:
            # Generate local filename using helper
            filename = create_filename(edition)

            # Store temporary files in the same location as tracking file
            # This keeps all job data in the persistent Azure File Share
            tracking_file = Path(self.settings.tracking.file_path)
            temp_dir = tracking_file.parent / "tmp"
            temp_path = temp_dir / filename

            # Ensure the tmp directory exists
            temp_path.parent.mkdir(parents=True, exist_ok=True)

            # Download the PDF
            await self.boersenmedien_client.download_edition(edition, str(temp_path))

            return str(temp_path)

        except Exception as e:
            logger.error("Download failed: %s", e)
            return None

    async def _download_latest_edition(self) -> tuple[Optional[Edition], Optional[str]]:
        """Download the latest edition from boersenmedien.com (legacy method for compatibility)."""
        edition = await self._get_latest_edition_info()
        if not edition:
            return None, None

        download_path = await self._download_edition(edition)
        return edition, download_path

    async def _upload_to_onedrive(
        self, edition: Edition, local_path: str
    ) -> UploadResult:
        """Upload file to OneDrive."""
        try:
            # Authenticate with OneDrive
            auth_success = await self.onedrive_service.authenticate()
            if not auth_success:
                return UploadResult(
                    success=False, error="OneDrive authentication failed"
                )

            # Upload file to OneDrive (folder path is handled internally based on settings)
            upload_result = await self.onedrive_service.upload_file(
                local_file_path=local_path, edition=edition
            )

            return upload_result

        except Exception as e:
            logger.error("OneDrive upload error: %s", e)
            return UploadResult(success=False, error=str(e))

    async def _send_pdf_email(self, edition: Edition, pdf_path: str) -> bool:
        """Send PDF file via email to all recipients."""
        try:
            success = await self.email_service.send_pdf_to_recipients(
                pdf_path=pdf_path, edition=edition
            )
            if success:
                logger.info("📧 PDF successfully sent via email to all recipients")
            else:
                logger.error("📧 Failed to send PDF via email to some/all recipients")
            return success

        except Exception as e:
            logger.error("Error sending PDF via email: %s", e)
            return False

    async def _send_success_notification(
        self, edition: Edition, upload_result: UploadResult
    ):
        """Send email notification for successful upload."""
        try:
            success = await self.email_service.send_success_notification(
                edition=edition,
                onedrive_url=upload_result.file_url or "URL nicht verfügbar",
            )
            if success:
                logger.info("✅ Success notification sent for: %s", edition.title)
            else:
                logger.warning("⚠️ Failed to send success notification")

        except Exception as e:
            logger.error("Error sending success notification: %s", e)

    async def _send_error_notification(
        self, edition: Optional[Edition], error_msg: str
    ):
        """Send email notification for workflow errors."""
        try:
            edition_title = edition.title if edition else None
            success = await self.email_service.send_error_notification(
                error_msg=error_msg, edition_title=edition_title
            )
            if success:
                logger.info("📧 Error notification sent")
            else:
                logger.warning("⚠️ Failed to send error notification")

        except Exception as e:
            logger.error("Error sending error notification: %s", e)

    async def check_for_new_editions(self) -> dict:
        """
        Check for new editions without processing them.
        Useful for status checks and monitoring.

        Returns:
            Dict with information about available editions
        """
        try:
            edition = await self._get_latest_edition_info()
            if not edition:
                return {"success": False, "error": "Failed to get edition information"}

            is_processed = self.edition_tracker.is_already_processed(edition)
            recent_editions = self.edition_tracker.get_recent_editions(7)  # Last 7 days

            return {
                "success": True,
                "latest_edition": {
                    "title": edition.title,
                    "publication_date": edition.publication_date,
                    "already_processed": is_processed,
                },
                "recent_processed_count": len(recent_editions),
                "total_processed_count": self.edition_tracker.get_processed_count(),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def force_reprocess_latest(self) -> dict:
        """
        Force reprocessing of the latest edition even if already processed.
        Useful for testing or when reprocessing is needed.
        """
        try:
            edition = await self._get_latest_edition_info()
            if not edition:
                return {"success": False, "error": "Failed to get edition information"}

            # Remove from tracking to allow reprocessing
            was_tracked = self.edition_tracker.force_reprocess(edition)

            # Run the workflow
            result = await self.run_full_workflow()
            result["was_previously_processed"] = was_tracked

            return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _cleanup_files(self, file_path: str):
        """Remove temporary downloaded files."""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info("Cleaned up temporary file: %s", file_path)
        except Exception as e:
            logger.warning("Failed to cleanup file %s: %s", file_path, e)


# Main entry point for Azure Container or scheduled execution
async def main():
    """
    Main entry point for the DepotButler workflow.
    Designed to run in Azure Container Instance as scheduled job.
    """
    async with DepotButlerWorkflow() as workflow:
        result = await workflow.run_full_workflow()

        # Return appropriate exit code for container scheduling
        if result["success"]:
            logger.info("Workflow completed successfully")
            return 0
        else:
            logger.error("Workflow failed: %s", result["error"])
            return 1


if __name__ == "__main__":
    # For testing locally
    exit_code = asyncio.run(main())
    exit(exit_code)
