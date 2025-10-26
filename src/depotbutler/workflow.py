"""
Main workflow orchestrator for DepotButler.
Coordinates downloading, uploading to OneDrive, and email notifications.
"""

import asyncio
import os
from pathlib import Path
from typing import Optional

from depotbutler.client import MegatrendClient
from depotbutler.mailer import EmailService
from depotbutler.models import Edition, UploadResult
from depotbutler.onedrive import OneDriveService
from depotbutler.settings import Settings
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


class DepotButlerWorkflow:
    """
    Main workflow orchestrator for automated PDF processing.

    Workflow:
    1. Login to Megatrend and download latest edition
    2. Upload PDF to OneDrive
    3. Send email notification (success/failure)
    4. Cleanup temporary files
    """

    def __init__(self):
        self.settings = Settings()
        self.megatrend_client: Optional[MegatrendClient] = None
        self.onedrive_service: Optional[OneDriveService] = None
        self.email_service: Optional[EmailService] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.megatrend_client = MegatrendClient()
        self.onedrive_service = OneDriveService()
        self.email_service = EmailService()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup."""
        if self.megatrend_client:
            await self.megatrend_client.close()
        if self.onedrive_service:
            await self.onedrive_service.close()

    async def run_full_workflow(self) -> dict:
        """
        Execute the complete DepotButler workflow.

        Returns:
            Dict with workflow results and status information
        """
        workflow_result = {
            "success": False,
            "edition": None,
            "download_path": None,
            "upload_result": None,
            "error": None,
        }

        try:
            logger.info("🚀 Starting DepotButler workflow")

            # Step 1: Download latest edition
            logger.info("📥 Step 1: Downloading latest edition")
            edition, download_path = await self._download_latest_edition()
            workflow_result["edition"] = edition
            workflow_result["download_path"] = download_path

            if not edition or not download_path:
                raise Exception("Failed to download latest edition")

            # Step 2: Send PDF via email
            logger.info("📧 Step 2: Sending PDF via email")
            email_success = await self._send_pdf_email(edition, download_path)
            if not email_success:
                logger.warning("Email sending failed, but continuing with workflow")

            # Step 3: Upload to OneDrive
            logger.info("☁️ Step 3: Uploading to OneDrive")
            upload_result = await self._upload_to_onedrive(edition, download_path)
            workflow_result["upload_result"] = upload_result

            if not upload_result.success:
                raise Exception(f"OneDrive upload failed: {upload_result.error}")

            # Step 4: Send success notification
            logger.info("✅ Step 4: Sending success notification")
            await self._send_success_notification(edition, upload_result)

            # Step 5: Cleanup
            logger.info("🧹 Step 5: Cleaning up temporary files")
            await self._cleanup_files(download_path)

            workflow_result["success"] = True
            logger.info("✅ DepotButler workflow completed successfully!")

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

    async def _download_latest_edition(self) -> tuple[Optional[Edition], Optional[str]]:
        """Download the latest edition from Megatrend."""
        try:
            # Login to Megatrend
            await self.megatrend_client.login()

            # Get latest edition info
            edition = await self.megatrend_client.get_latest_edition()
            logger.info(f"Found edition: {edition.title}")

            # Get publication date
            edition = await self.megatrend_client.get_publication_date(edition)
            logger.info(f"Publication date: {edition.publication_date}")

            # Generate local filename using helper
            from depotbutler.utils.helpers import create_filename

            filename = create_filename(edition)
            temp_path = Path.cwd() / "tmp" / filename

            # Ensure the tmp directory exists
            temp_path.parent.mkdir(parents=True, exist_ok=True)

            # Download the PDF
            await self.megatrend_client.download_edition(edition, str(temp_path))

            return edition, str(temp_path)

        except Exception as e:
            logger.error(f"Download failed: {e}")
            return None, None

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
            logger.error(f"OneDrive upload error: {e}")
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
            logger.error(f"Error sending PDF via email: {e}")
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
                logger.info(f"✅ Success notification sent for: {edition.title}")
            else:
                logger.warning("⚠️ Failed to send success notification")

        except Exception as e:
            logger.error(f"Error sending success notification: {e}")

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
            logger.error(f"Error sending error notification: {e}")

    async def _cleanup_files(self, file_path: str):
        """Remove temporary downloaded files."""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Cleaned up temporary file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup file {file_path}: {e}")


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
            logger.error(f"Workflow failed: {result['error']}")
            return 1


if __name__ == "__main__":
    # For testing locally
    exit_code = asyncio.run(main())
    exit(exit_code)
