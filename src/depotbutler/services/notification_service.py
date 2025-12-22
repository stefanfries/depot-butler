"""Notification service for workflow results."""

from __future__ import annotations

from typing import TYPE_CHECKING

from depotbutler.utils.logger import get_logger

if TYPE_CHECKING:
    from depotbutler.mailer import EmailService
    from depotbutler.models import Edition, UploadResult
    from depotbutler.services.publication_processor import PublicationResult

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

            # Build summary
            succeeded = [r for r in results if r.success and not r.already_processed]
            skipped = [r for r in results if r.already_processed]
            failed = [r for r in results if not r.success and not r.already_processed]

            # Build HTML message
            html_parts = [
                "<h2>📊 DepotButler Daily Report</h2>",
                "<p style='border-bottom: 2px solid #ddd; padding-bottom: 10px;'>",
                f"<strong>Processed:</strong> {len(results)} publication(s)<br>",
                f"✅ <strong>Success:</strong> {len(succeeded)} | "
                f"ℹ️ <strong>Skipped:</strong> {len(skipped)} | "
                f"❌ <strong>Failed:</strong> {len(failed)}",
                "</p>",
            ]

            # Add successful publications
            if succeeded:
                html_parts.append("<h3>✅ New Editions Processed</h3>")
                for result in succeeded:
                    # Email status
                    email_status = (
                        "✅ Sent"
                        if result.email_result is True
                        else (
                            "❌ Failed"
                            if result.email_result is False
                            else "⏭️ Disabled"
                        )
                    )

                    # OneDrive status
                    onedrive_link = ""
                    if result.upload_result and result.upload_result.file_url:
                        onedrive_link = f"<br>📎 <a href='{result.upload_result.file_url}'>View in OneDrive</a>"

                    html_parts.append(
                        f"<div style='margin: 15px 0; padding: 10px; background: #f0f9ff; border-left: 4px solid #0066cc;'>"
                        f"<strong>{result.edition.title if result.edition else result.publication_name}</strong><br>"
                        f"Published: {result.edition.publication_date if result.edition else 'Unknown'}<br>"
                        f"📧 Email: {email_status}"
                        f"{onedrive_link}"
                        f"</div>"
                    )

            # Add skipped publications
            if skipped:
                html_parts.append("<h3>ℹ️ Already Processed</h3>")
                for result in skipped:
                    html_parts.append(
                        f"<div style='margin: 10px 0; padding: 8px; background: #f5f5f5; border-left: 4px solid #999;'>"
                        f"{result.edition.title if result.edition else result.publication_name}<br>"
                        f"<small>Processed: {result.edition.publication_date if result.edition else 'Unknown'}</small>"
                        f"</div>"
                    )

            # Add failed publications
            if failed:
                html_parts.append("<h3>❌ Failed</h3>")
                for result in failed:
                    html_parts.append(
                        f"<div style='margin: 10px 0; padding: 10px; background: #fff0f0; border-left: 4px solid #cc0000;'>"
                        f"<strong>{result.publication_name}</strong><br>"
                        f"Error: {result.error or 'Unknown error'}"
                        f"</div>"
                    )

            html_message = "".join(html_parts)

            # Determine notification type
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
                # Use first successful edition for compatibility
                first_edition = succeeded[0].edition if succeeded else None
                if first_edition:
                    # Send enhanced notification with summary
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

            logger.info("📧 Consolidated notification sent")

        except Exception as e:
            logger.error(f"Error sending consolidated notification: {e}", exc_info=True)
