"""Notification service for workflow results."""

from __future__ import annotations

from typing import TYPE_CHECKING

from depotbutler.models import PublicationResult
from depotbutler.utils.logger import get_logger

if TYPE_CHECKING:
    from depotbutler.mailer import EmailService
    from depotbutler.models import Edition, UploadResult

logger = get_logger(__name__)


class NotificationService:
    """Service for sending workflow notifications to administrators."""

    def __init__(self, email_service: EmailService, dry_run: bool = False):
        """
        Initialize notification service.

        Args:
            email_service: Email service for sending notifications
            dry_run: If True, log actions without sending emails
        """
        self.email_service = email_service
        self.dry_run = dry_run

    async def send_success_notification(
        self, edition: Edition, upload_result: UploadResult
    ) -> None:
        """
        Send email notification for successful upload.

        Args:
            edition: Edition that was processed
            upload_result: OneDrive upload result
        """
        try:
            if self.dry_run:
                logger.info(
                    "🧪 DRY-RUN: Would send success notification for: %s", edition.title
                )
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

    async def send_error_notification(
        self, edition: Edition | None, error_msg: str
    ) -> None:
        """
        Send email notification for workflow errors.

        Args:
            edition: Edition that failed (None if error before edition retrieval)
            error_msg: Error message to include
        """
        try:
            if self.dry_run:
                dry_run_title = edition.title if edition else "Unknown"
                logger.info(
                    "🧪 DRY-RUN: Would send error notification for: %s", dry_run_title
                )
                return

            edition_title: str | None = edition.title if edition else None
            success = await self.email_service.send_error_notification(
                error_msg=error_msg, edition_title=edition_title
            )
            if success:
                logger.info("📧 Error notification sent")
            else:
                logger.warning("⚠️ Failed to send error notification")

        except Exception as e:
            logger.error("Error sending error notification: %s", e)

    async def send_consolidated_notification(
        self, results: list[PublicationResult]
    ) -> None:
        """
        Send consolidated email notification for all processed publications.

        Args:
            results: List of PublicationResult objects from processing
        """
        try:
            if self.dry_run:
                logger.info(
                    "🧪 DRY-RUN: Would send consolidated notification for %d publication(s)",
                    len(results),
                )
                return

            # Categorize and send notification
            succeeded, skipped, failed = self._categorize_results(results)
            html_message = self._build_consolidated_report(
                results, succeeded, skipped, failed
            )
            await self._send_notification_by_status(
                succeeded, skipped, failed, html_message
            )

            logger.info("📧 Consolidated notification sent")

        except Exception as e:
            logger.error(f"Error sending consolidated notification: {e}", exc_info=True)

    def _categorize_results(
        self, results: list[PublicationResult]
    ) -> tuple[
        list[PublicationResult], list[PublicationResult], list[PublicationResult]
    ]:
        """
        Categorize results into succeeded, skipped, and failed.

        Returns:
            Tuple of (succeeded, skipped, failed) result lists
        """
        succeeded = [r for r in results if r.success and not r.already_processed]
        skipped = [r for r in results if r.already_processed]
        failed = [r for r in results if not r.success and not r.already_processed]
        return succeeded, skipped, failed

    def _build_consolidated_report(
        self,
        results: list[PublicationResult],
        succeeded: list[PublicationResult],
        skipped: list[PublicationResult],
        failed: list[PublicationResult],
    ) -> str:
        """
        Build HTML report for consolidated notification.

        Args:
            results: All results
            succeeded: Successful results
            skipped: Skipped results
            failed: Failed results

        Returns:
            HTML message string
        """
        html_parts = self._build_report_header(results, succeeded, skipped, failed)

        if succeeded:
            html_parts.extend(self._build_success_section(succeeded))

        if skipped:
            html_parts.extend(self._build_skipped_section(skipped))

        if failed:
            html_parts.extend(self._build_failed_section(failed))

        return "".join(html_parts)

    def _build_report_header(
        self,
        results: list[PublicationResult],
        succeeded: list[PublicationResult],
        skipped: list[PublicationResult],
        failed: list[PublicationResult],
    ) -> list[str]:
        """Build header section of report."""
        return [
            "<h2>📊 DepotButler Daily Report</h2>",
            "<p style='border-bottom: 2px solid #ddd; padding-bottom: 10px;'>",
            f"<strong>Processed:</strong> {len(results)} publication(s)<br>",
            f"✅ <strong>Success:</strong> {len(succeeded)} | "
            f"ℹ️ <strong>Skipped:</strong> {len(skipped)} | "
            f"❌ <strong>Failed:</strong> {len(failed)}",
            "</p>",
        ]

    def _build_success_section(self, succeeded: list[PublicationResult]) -> list[str]:
        """Build success section of report."""
        html_parts = ["<h3>✅ New Editions Processed</h3>"]

        for result in succeeded:
            email_status = self._get_email_status(result)
            onedrive_link = self._get_onedrive_link(result)
            archival_status = self._get_archival_status(result)

            html_parts.append(
                f"<div style='margin: 10px 0; padding: 10px; background: #f0fff0; border-left: 4px solid #00cc00;'>"
                f"<strong>{result.edition.title if result.edition else result.publication_name}</strong><br>"
                f"<small>Published: {result.edition.publication_date if result.edition else 'Unknown'}</small><br>"
                f"📧 Email: {email_status}"
                f"{onedrive_link}"
                f"{archival_status}"
                f"</div>"
            )

        return html_parts

    def _build_skipped_section(self, skipped: list[PublicationResult]) -> list[str]:
        """Build skipped section of report."""
        html_parts = ["<h3>ℹ️ Already Processed</h3>"]

        for result in skipped:
            html_parts.append(
                f"<div style='margin: 10px 0; padding: 8px; background: #f5f5f5; border-left: 4px solid #999;'>"
                f"{result.edition.title if result.edition else result.publication_name}<br>"
                f"<small>Processed: {result.edition.publication_date if result.edition else 'Unknown'}</small>"
                f"</div>"
            )

        return html_parts

    def _build_failed_section(self, failed: list[PublicationResult]) -> list[str]:
        """Build failed section of report."""
        html_parts = ["<h3>❌ Failed</h3>"]

        for result in failed:
            html_parts.append(
                f"<div style='margin: 10px 0; padding: 10px; background: #fff0f0; border-left: 4px solid #cc0000;'>"
                f"<strong>{result.publication_name}</strong><br>"
                f"Error: {result.error or 'Unknown error'}"
                f"</div>"
            )

        return html_parts

    def _get_email_status(self, result: PublicationResult) -> str:
        """Get formatted email status string."""
        if result.email_result is True:
            return "✅ Sent"
        elif result.email_result is False:
            return "❌ Failed"
        else:
            return "⏭️ Disabled"

    def _get_onedrive_link(self, result: PublicationResult) -> str:
        """Get formatted OneDrive link HTML."""
        if result.upload_result and result.upload_result.file_url:
            file_url = result.upload_result.file_url

            # Check if file_url contains URL with recipient count (format: "url|count")
            if "|" in file_url:
                url, count = file_url.split("|", 1)
                return f"<br>📎 <a href='{url}'>Uploaded to OneDrive</a> ({count} recipient(s))"
            # Single recipient or direct URL
            elif file_url.startswith("http"):
                return f"<br>📎 <a href='{file_url}'>View in OneDrive</a>"
            else:
                # Fallback for recipient count without URL
                return f"<br>📎 Uploaded to OneDrive ({file_url})"
        return ""

    def _get_archival_status(self, result: PublicationResult) -> str:
        """Get formatted archival status string."""
        if result.archived is True:
            return "<br>☁️ Archival: ✅ Archived to Blob Storage"
        elif result.archived is False:
            return "<br>☁️ Archival: ⚠️ Failed (workflow continued)"
        else:
            return ""  # Not attempted (blob storage not configured)

    async def _send_notification_by_status(
        self,
        succeeded: list[PublicationResult],
        skipped: list[PublicationResult],
        failed: list[PublicationResult],
        html_message: str,
    ) -> None:
        """
        Send notification based on processing status.

        Args:
            succeeded: Successful results
            skipped: Skipped results
            failed: Failed results
            html_message: Pre-built HTML message
        """
        if failed and not succeeded:
            # All failed - send error notification
            await self.email_service.send_error_notification(
                error_msg=html_message,
                edition_title="All Publications Failed",
            )
        elif failed:
            # Some failed - send warning
            await self.email_service.send_warning_notification(
                warning_msg=html_message,
            )
        elif succeeded:
            # All succeeded or skipped - send success
            first_edition = succeeded[0].edition
            if first_edition:
                await self.email_service.send_success_notification(
                    edition=first_edition,
                    onedrive_url=html_message,  # Pass HTML summary
                )
        else:
            # All skipped - send info notification
            await self.email_service.send_warning_notification(
                warning_msg=html_message,
                title="DepotButler: No New Editions",
            )
