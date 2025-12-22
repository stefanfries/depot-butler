"""Email service for sending PDF attachments and notifications."""

import smtplib
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from time import perf_counter

from depotbutler.db import get_active_recipients, update_recipient_stats
from depotbutler.db.mongodb import get_mongodb_service, get_recipients_for_publication
from depotbutler.exceptions import EmailDeliveryError
from depotbutler.mailer.composers import (
    create_error_notification_message,
    create_pdf_attachment_message,
    create_success_notification_message,
    create_warning_notification_message,
)
from depotbutler.models import Edition
from depotbutler.settings import Settings
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


class EmailService:
    """Email service for sending notifications and PDF attachments."""

    def __init__(self) -> None:
        self.settings = Settings()
        self.mail_settings = self.settings.mail

    async def _get_admin_emails(self) -> list[str]:
        """Get admin email addresses from MongoDB config, with fallback to settings.

        Returns:
            List of admin email addresses
        """
        try:
            mongodb = await get_mongodb_service()
            admin_emails = await mongodb.get_app_config("admin_emails")

            if admin_emails and isinstance(admin_emails, list):
                return list(admin_emails)
        except Exception as e:
            logger.warning(f"Could not load admin_emails from MongoDB: {e}")

        # Fallback to .env setting
        return [str(self.mail_settings.admin_address)]

    async def send_pdf_to_recipients(
        self, pdf_path: str, edition: Edition, publication_id: str | None = None
    ) -> bool:
        """Send PDF file as attachment to recipients subscribed to a publication.

        Args:
            pdf_path: Path to the PDF file
            edition: Edition information for email content
            publication_id: Publication ID to filter recipients (None = legacy behavior)

        Returns:
            True if all emails sent successfully, False otherwise
        """
        try:
            if not Path(pdf_path).exists():
                logger.error("PDF file not found: %s", pdf_path)
                return False

            # Fetch recipients based on publication_id
            if publication_id:
                recipient_docs = await get_recipients_for_publication(
                    publication_id, "email"
                )
                logger.info(
                    "📧 Starting email distribution for publication=%s [recipient_count=%s, edition=%s]",
                    publication_id,
                    len(recipient_docs),
                    edition.title,
                )
            else:
                # Legacy: Get all active recipients
                recipient_docs = await get_active_recipients()
                logger.info(
                    "📧 Starting email distribution (legacy mode) [recipient_count=%s, edition=%s]",
                    len(recipient_docs),
                    edition.title,
                )

            if not recipient_docs:
                logger.warning("No recipients found for this publication")
                return True  # Not an error, just no one to send to

            success_count = 0
            send_start = perf_counter()

            for idx, recipient_doc in enumerate(recipient_docs, 1):
                recipient_email = recipient_doc["email"]
                firstname = recipient_doc.get("first_name", "Abonnent")

                recipient_start = perf_counter()
                success = await self._send_individual_email(
                    pdf_path, edition, recipient_email, firstname
                )
                recipient_elapsed = perf_counter() - recipient_start

                if success:
                    success_count += 1
                    logger.info(
                        "✅ Email sent successfully [%s/%s] [recipient=%s, time=%.2fs]",
                        idx,
                        len(recipient_docs),
                        recipient_email,
                        recipient_elapsed,
                    )
                    # Update recipient statistics in MongoDB (per-publication if provided)
                    await update_recipient_stats(recipient_email, publication_id)
                else:
                    logger.error(
                        "❌ Failed to send email [%s/%s] [recipient=%s, time=%.2fs]",
                        idx,
                        len(recipient_docs),
                        recipient_email,
                        recipient_elapsed,
                    )

            total_elapsed = perf_counter() - send_start
            logger.info(
                "📧 Email distribution completed [success=%s/%s, total_time=%.2fs, avg_time=%.2fs]",
                success_count,
                len(recipient_docs),
                total_elapsed,
                total_elapsed / len(recipient_docs),
            )
            return success_count == len(recipient_docs)

        except Exception as e:
            logger.error("Error sending PDF emails: %s", e)
            return False

    async def _send_individual_email(
        self, pdf_path: str, edition: Edition, recipient: str, firstname: str
    ) -> bool:
        """Send email with PDF attachment to a single recipient.

        Args:
            pdf_path: Path to PDF file
            edition: Edition information
            recipient: Recipient email address
            firstname: Recipient's first name

        Returns:
            True if email sent successfully
        """
        try:
            # Create MIME message using composer
            msg = create_pdf_attachment_message(
                pdf_path, edition, recipient, firstname, self.mail_settings.username
            )

            # Send email
            await self._send_smtp_email(msg, recipient)
            logger.info("Successfully sent email to %s", recipient)
            return True

        except Exception as e:
            logger.error("Error sending email to %s: %s", recipient, e)
            return False

    async def _send_smtp_email(self, msg: MIMEMultipart, recipient: str) -> bool:
        """Send email via SMTP with settings from MongoDB.

        Args:
            msg: MIME message to send
            recipient: Recipient email address

        Returns:
            True if email sent successfully

        Raises:
            EmailDeliveryError: If email sending fails
        """
        try:
            # Get SMTP settings from MongoDB with fallback to .env
            mongodb = await get_mongodb_service()
            smtp_server = await mongodb.get_app_config(
                "smtp_server", default=self.mail_settings.server
            )
            smtp_port = await mongodb.get_app_config(
                "smtp_port", default=self.mail_settings.port
            )

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()  # Enable encryption
                server.login(
                    self.mail_settings.username,
                    self.mail_settings.password.get_secret_value(),
                )
                server.send_message(msg)

            return True

        except smtplib.SMTPException as e:
            logger.error("SMTP error sending to %s: %s", recipient, e)
            raise EmailDeliveryError(f"Failed to send email to {recipient}: {e}") from e
        except Exception as e:
            logger.error("Unexpected error sending to %s: %s", recipient, e)
            raise EmailDeliveryError(
                f"Unexpected error sending email to {recipient}: {e}"
            ) from e

    async def send_success_notification(
        self, edition: Edition, onedrive_url: str
    ) -> bool:
        """Send success notification email to admin.

        Args:
            edition: Edition information
            onedrive_url: URL to the file in OneDrive or HTML summary

        Returns:
            True if email sent successfully to all admins
        """
        try:
            # Send notification to all admin emails
            admin_emails = await self._get_admin_emails()
            all_success = True

            for admin_email in admin_emails:
                success = await self._send_success_email(
                    edition, onedrive_url, admin_email
                )

                if success:
                    logger.info("Sent success notification to admin: %s", admin_email)
                else:
                    logger.warning(
                        "Failed to send success notification to admin: %s", admin_email
                    )
                    all_success = False

            return all_success

        except Exception as e:
            logger.error("Error sending success notification: %s", e)
            return False

    async def _send_success_email(
        self,
        edition: Edition,
        onedrive_url: str,
        recipient: str,
        firstname: str | None = None,
    ) -> bool:
        """Send success notification to single recipient.

        Args:
            edition: Edition information
            onedrive_url: URL to file or HTML summary for consolidated reports
            recipient: Recipient email address
            firstname: Recipient's first name (if None, extracts from email)

        Returns:
            True if email sent successfully
        """
        try:
            # Create MIME message using composer
            msg = create_success_notification_message(
                edition, onedrive_url, recipient, firstname, self.mail_settings.username
            )

            await self._send_smtp_email(msg, recipient)
            return True

        except Exception as e:
            logger.error("Error sending success email to %s: %s", recipient, e)
            return False

    async def send_warning_notification(
        self,
        warning_msg: str,
        title: str = "System Warning",
    ) -> bool:
        """Send warning notification email to admin.

        Args:
            warning_msg: Warning message
            title: Warning title

        Returns:
            True if email sent successfully to all admins
        """
        try:
            # Send warning notification to all admin emails
            admin_emails = await self._get_admin_emails()
            all_success = True

            for admin_email in admin_emails:
                success = await self._send_warning_email(
                    warning_msg, title, admin_email
                )

                if success:
                    logger.info("Sent warning notification to admin: %s", admin_email)
                else:
                    logger.warning(
                        "Failed to send warning notification to admin: %s", admin_email
                    )
                    all_success = False

            return all_success

        except Exception as e:
            logger.error("Error sending warning notification: %s", e)
            return False

    async def _send_warning_email(
        self, warning_msg: str, title: str, recipient: str, firstname: str | None = None
    ) -> bool:
        """Send warning email to recipient.

        Args:
            warning_msg: Warning message
            title: Warning title
            recipient: Recipient email address
            firstname: Recipient's first name (if None, extracts from email)

        Returns:
            True if email sent successfully
        """
        try:
            # Create MIME message using composer
            msg = create_warning_notification_message(
                warning_msg, title, recipient, firstname, self.mail_settings.username
            )

            await self._send_smtp_email(msg, recipient)
            return True

        except Exception as e:
            logger.error("Error sending warning email to %s: %s", recipient, e)
            return False

    async def send_error_notification(
        self,
        error_msg: str,
        edition_title: str | None = None,
        recipients: list[str] | None = None,
    ) -> bool:
        """Send error notification email to admin.

        Args:
            error_msg: Error message
            edition_title: Optional edition title if available
            recipients: Optional list of recipients (ignored, uses admin_address)

        Returns:
            True if email sent successfully to all admins
        """
        try:
            # Send error notification to all admin emails
            admin_emails = await self._get_admin_emails()
            all_success = True

            for admin_email in admin_emails:
                success = await self._send_error_email(
                    error_msg, edition_title, admin_email
                )

                if success:
                    logger.info("Sent error notification to admin: %s", admin_email)
                else:
                    logger.warning(
                        "Failed to send error notification to admin: %s", admin_email
                    )
                    all_success = False

            return all_success

        except Exception as e:
            logger.error("Error sending error notification: %s", e)
            return False

    async def _send_error_email(
        self,
        error_msg: str,
        edition_title: str | None,
        recipient: str,
        firstname: str | None = None,
    ) -> bool:
        """Send error email to recipient.

        Args:
            error_msg: Error message
            edition_title: Edition title if available
            recipient: Recipient email address
            firstname: Recipient's first name (if None, extracts from email)

        Returns:
            True if email sent successfully
        """
        try:
            # Create MIME message using composer
            msg = create_error_notification_message(
                error_msg,
                edition_title,
                recipient,
                firstname,
                self.mail_settings.username,
            )

            await self._send_smtp_email(msg, recipient)
            return True

        except Exception as e:
            logger.error("Error sending error email to %s: %s", recipient, e)
            return False
