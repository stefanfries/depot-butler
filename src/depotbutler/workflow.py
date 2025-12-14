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

from depotbutler.db.mongodb import (
    close_mongodb_connection,
    get_mongodb_service,
    get_publications,
)
from depotbutler.discovery import PublicationDiscoveryService
from depotbutler.edition_tracker import EditionTracker
from depotbutler.httpx_client import HttpxBoersenmedienClient
from depotbutler.mailer import EmailService
from depotbutler.models import Edition, UploadResult
from depotbutler.onedrive import OneDriveService
from depotbutler.publications import PublicationConfig
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

    def __init__(self, tracking_file_path: Optional[str] = None, dry_run: bool = False):
        self.settings = Settings()
        self.boersenmedien_client: Optional[HttpxBoersenmedienClient] = None
        self.onedrive_service: Optional[OneDriveService] = None
        self.email_service: Optional[EmailService] = None
        self.dry_run = dry_run

        if dry_run:
            logger.warning("🧪 DRY-RUN MODE: No emails will be sent and no files will be uploaded")

        # Note: tracking_file_path parameter is deprecated and ignored
        # Edition tracking now uses MongoDB
        if tracking_file_path:
            logger.warning(
                "tracking_file_path parameter is deprecated - using MongoDB for tracking"
            )

        # Initialize edition tracker - will be upgraded to MongoDB in __aenter__
        # For testing/backwards compatibility, create a sync-compatible dummy tracker
        class SyncDummyTracker:
            """Dummy tracker for testing that supports both sync and async patterns."""

            def is_already_processed(self, edition):  # noqa: ARG002
                return False

            def mark_as_processed(self, edition, file_path=""):  # noqa: ARG002
                pass

            def get_processed_count(self):
                return 0

            def get_recent_editions(self, days):  # noqa: ARG002
                return []

            def force_reprocess(self, edition):  # noqa: ARG002
                return False

        self.edition_tracker = (
            SyncDummyTracker()
            if not self.settings.tracking.enabled
            else SyncDummyTracker()
        )
        if not self.settings.tracking.enabled:
            logger.info("Edition tracking is disabled")

    async def __aenter__(self):
        """Async context manager entry."""
        # Use HTTPX-based client (lightweight, no browser needed)
        self.boersenmedien_client = HttpxBoersenmedienClient()
        self.onedrive_service = OneDriveService()
        self.email_service = EmailService()

        # Initialize real edition tracker with MongoDB (if tracking is enabled and not mocked)
        if self.settings.tracking.enabled and not hasattr(
            self.edition_tracker, "_test_mock"
        ):
            mongodb = await get_mongodb_service()

            # Get tracking settings from MongoDB with fallback to .env
            tracking_enabled = await mongodb.get_app_config(
                "tracking_enabled", default=self.settings.tracking.enabled
            )
            retention_days = await mongodb.get_app_config(
                "tracking_retention_days", default=self.settings.tracking.retention_days
            )

            if tracking_enabled:
                self.edition_tracker = EditionTracker(
                    mongodb=mongodb,
                    retention_days=retention_days,
                )
                logger.info(
                    "Edition tracking enabled with MongoDB backend [retention_days=%s]",
                    retention_days,
                )
            else:
                logger.info("Edition tracking is disabled via MongoDB config")

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

            # Step 0: Check cookie expiration and send warning if needed
            await self._check_and_notify_cookie_expiration()

            # Step 1: Login to boersenmedien.com
            logger.info("🔐 Step 1: Authenticating")
            await self.boersenmedien_client.login()
            await self.boersenmedien_client.discover_subscriptions()

            # Step 2: Sync publications from account (if enabled) - updates MongoDB
            if self.settings.discovery.enabled:
                logger.info("🔄 Step 2: Syncing publications from account")
                await self._sync_publications_from_account()

            # Step 3: Get latest edition info from fresh MongoDB data
            logger.info("📋 Step 3: Checking for new editions")
            edition = await self._get_latest_edition_info()
            workflow_result["edition"] = edition

            if not edition:
                raise Exception("Failed to get latest edition information")

            # Step 4: Check if already processed
            if await self.edition_tracker.is_already_processed(edition):
                logger.info(
                    f"✅ Edition already processed: {edition.title} ({edition.publication_date})"
                )
                workflow_result["already_processed"] = True
                workflow_result["success"] = True
                return workflow_result

            logger.info(
                f"📥 New edition found: {edition.title} ({edition.publication_date})"
            )

            # Step 5: Download the edition
            logger.info("📥 Step 5: Downloading new edition")
            download_path = await self._download_edition(edition)
            workflow_result["download_path"] = download_path

            if not download_path:
                raise Exception("Failed to download edition")

            # Step 6: Send PDF via email (if enabled for this publication)
            email_enabled = self.current_publication_data.get("email_enabled", True)
            if email_enabled:
                logger.info("📧 Step 6: Sending PDF via email")
                email_success = await self._send_pdf_email(edition, download_path)
                if not email_success:
                    logger.warning("Email sending failed, but continuing with workflow")
            else:
                logger.info("📧 Step 6: Email disabled for this publication, skipping")

            # Step 7: Upload to OneDrive (if enabled for this publication)
            onedrive_enabled = self.current_publication_data.get(
                "onedrive_enabled", True
            )
            if onedrive_enabled:
                logger.info("☁️ Step 7: Uploading to OneDrive")
                upload_result = await self._upload_to_onedrive(edition, download_path)
                workflow_result["upload_result"] = upload_result

                if not upload_result.success:
                    raise Exception(f"OneDrive upload failed: {upload_result.error}")
            else:
                logger.info(
                    "☁️ Step 7: OneDrive disabled for this publication, skipping"
                )
                # Create a dummy success result
                upload_result = UploadResult(
                    success=True,
                    file_url="N/A (OneDrive disabled)",
                    file_id="N/A",
                )
                workflow_result["upload_result"] = upload_result

            # Step 6: Mark as processed (do this before notifications to ensure it's recorded)
            await self.edition_tracker.mark_as_processed(edition, download_path)
            logger.info("✅ Edition marked as processed")

            # Step 8: Send success notification
            logger.info("📧 Step 7: Sending success notification")
            await self._send_success_notification(edition, upload_result)

            # Step 10: Cleanup
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
        """Get information about the latest edition without downloading.
        
        Note: Assumes client is already logged in and subscriptions are discovered.
        """
        try:
            # Get active publications from MongoDB (fresh from sync)
            publications = await get_publications(active_only=True)
            if not publications:
                logger.error("No active publications found in MongoDB")
                return None

            # Process first active publication (for now - will be expanded later)
            self.current_publication_data = publications[0]
            logger.info(
                "Processing publication: %s", self.current_publication_data["name"]
            )
            logger.info(
                "  Email enabled: %s | OneDrive enabled: %s",
                self.current_publication_data.get("email_enabled", True),
                self.current_publication_data.get("onedrive_enabled", True),
            )

            # Create PublicationConfig for compatibility with existing get_latest_edition
            publication = PublicationConfig(
                id=self.current_publication_data["publication_id"],
                name=self.current_publication_data["name"],
                onedrive_folder=self.current_publication_data.get(
                    "default_onedrive_folder", ""
                ),
                subscription_number=self.current_publication_data.get(
                    "subscription_number"
                ),
                subscription_id=self.current_publication_data.get("subscription_id"),
            )

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

    async def _sync_publications_from_account(self):
        """Synchronize publications from boersenmedien.com account to MongoDB."""
        try:
            logger.info("🔄 Syncing publications from account...")

            # Create discovery service
            discovery_service = PublicationDiscoveryService(self.boersenmedien_client)

            # Run synchronization
            sync_results = await discovery_service.sync_publications_from_account()

            # Log results
            if sync_results["new_count"] > 0:
                logger.info(
                    f"✨ Discovered {sync_results['new_count']} new publication(s)"
                )

            if sync_results["errors"]:
                logger.warning(
                    f"⚠️  Sync encountered {len(sync_results['errors'])} error(s)"
                )

            logger.info(
                f"✓ Publication sync complete: "
                f"{sync_results['discovered_count']} total, "
                f"{sync_results['updated_count']} updated"
            )

        except Exception as e:
            logger.error(f"Publication sync failed: {e}", exc_info=True)
            # Don't fail the entire workflow if sync fails
            logger.warning("Continuing workflow despite sync failure")

    async def _check_and_notify_cookie_expiration(self):
        """Check cookie expiration and send email notification if expiring soon."""
        try:
            mongodb = await get_mongodb_service()
            expiration_info = await mongodb.get_cookie_expiration_info()

            if not expiration_info:
                return

            days_remaining = expiration_info.get("days_remaining")
            is_expired = expiration_info.get("is_expired")
            expires_at = expiration_info.get("expires_at")

            # Get warning threshold from MongoDB config (default: 5 days)
            warning_days = await mongodb.get_app_config(
                "cookie_warning_days", default=5
            )

            # Only send WARNING notifications based on estimated expiration
            # Let actual login failures trigger error notifications
            if is_expired:
                logger.warning(
                    f"⚠️  Authentication cookie estimated to be expired (since {expires_at})"
                )
                logger.warning(
                    "   This is based on estimate. Actual login will be attempted."
                )
                # Send warning notification (not error) for estimated expiration
                await self.email_service.send_warning_notification(
                    warning_msg=f"The authentication cookie is estimated to have expired on {expires_at}.<br><br>"
                    f"This is only an estimate based on the manually entered expiration date. "
                    f"The system will still attempt to login. If the actual authentication fails, "
                    f"you will receive a separate error notification.<br><br>"
                    f"Please update the cookie soon using the following command:<br>"
                    f"<code>uv run python scripts/update_cookie_mongodb.py</code>",
                    title="Cookie Likely Expired",
                )
            elif days_remaining is not None and days_remaining <= warning_days:
                logger.warning(
                    f"⚠️  Authentication cookie expires in {days_remaining} days!"
                )
                await self.email_service.send_warning_notification(
                    warning_msg=f"The authentication cookie will expire in {days_remaining} days (on {expires_at}).<br><br>"
                    f"Please update it soon using the following command:<br>"
                    f"<code>uv run python scripts/update_cookie_mongodb.py</code>",
                    title="Cookie Expiring Soon",
                )

        except Exception as e:
            logger.error(f"Failed to check cookie expiration: {e}")

    async def _download_edition(self, edition: Edition) -> Optional[str]:
        """Download a specific edition."""
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
        """Upload file to OneDrive using publication-specific folder."""
        try:
            # Authenticate with OneDrive
            auth_success = await self.onedrive_service.authenticate()
            if not auth_success:
                return UploadResult(
                    success=False, error="OneDrive authentication failed"
                )

            # Get publication-specific OneDrive folder and organization preference
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
        """Send PDF file via email to recipients subscribed to current publication."""
        try:
            # Get publication_id from current_publication_data if available
            publication_id = None
            if self.current_publication_data:
                publication_id = self.current_publication_data.get("publication_id")

            if self.dry_run:
                logger.info("🧪 DRY-RUN: Would send email to recipients for publication_id=%s", publication_id)
                # In dry-run mode, still query recipients to show what would happen
                from depotbutler.db.mongodb import get_mongodb_service
                mongodb = await get_mongodb_service()
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

    async def _send_success_notification(
        self, edition: Edition, upload_result: UploadResult
    ):
        """Send email notification for successful upload."""
        try:
            if self.dry_run:
                logger.info("🧪 DRY-RUN: Would send success notification for: %s", edition.title)
                return

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
            if self.dry_run:
                edition_title = edition.title if edition else "Unknown"
                logger.info("🧪 DRY-RUN: Would send error notification for: %s", edition_title)
                return

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

            is_processed = await self.edition_tracker.is_already_processed(edition)
            recent_editions = await self.edition_tracker.get_recent_editions(
                7
            )  # Last 7 days

            return {
                "success": True,
                "latest_edition": {
                    "title": edition.title,
                    "publication_date": edition.publication_date,
                    "already_processed": is_processed,
                },
                "recent_processed_count": len(recent_editions),
                "total_processed_count": await self.edition_tracker.get_processed_count(),
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
            was_tracked = await self.edition_tracker.force_reprocess(edition)

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
