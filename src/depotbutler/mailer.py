"""
Email service for sending PDF attachments and notifications.
Supports SMTP with attachments and templated messages.
"""

import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from time import perf_counter

from depotbutler.db import get_active_recipients, update_recipient_stats
from depotbutler.db.mongodb import get_mongodb_service
from depotbutler.exceptions import EmailDeliveryError
from depotbutler.models import Edition
from depotbutler.settings import Settings
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


class EmailService:
    """
    Email service for sending notifications and PDF attachments.
    """

    def __init__(self) -> None:
        self.settings = Settings()
        self.mail_settings = self.settings.mail

    async def _get_admin_emails(self) -> list[str]:
        """
        Get admin email addresses from MongoDB config, with fallback to settings.

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
        """
        Send PDF file as attachment to recipients subscribed to a publication.

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
                from depotbutler.db.mongodb import get_recipients_for_publication

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
        """Send email with PDF attachment to a single recipient."""
        try:
            # Create message with mixed subtype for attachments
            msg = MIMEMultipart("mixed")

            # Email headers
            filename = Path(pdf_path).name
            msg["From"] = self.mail_settings.username
            msg["To"] = recipient
            msg["Subject"] = f"Neue Ausgabe {edition.title} verfügbar"

            # Create email body from template
            html_body = self._create_email_body(edition, filename, firstname)

            # Create plain text version as fallback
            plain_text = f"""
Hallo {firstname},

die neue Ausgabe {edition.title} vom {edition.publication_date} ist verfügbar und wurde automatisch für dich heruntergeladen.

Details:
- Titel: {edition.title}
- Ausgabedatum: {edition.publication_date}
- Dateiname: {filename}

Die PDF-Datei findest du im Anhang dieser E-Mail.

Viel Erfolg beim Trading!

Diese E-Mail wurde automatisch von Depot Butler generiert.
Depot Butler - Automatisierte Finanzpublikationen
            """.strip()

            # Create multipart/alternative for text content
            msg_alternative = MIMEMultipart("alternative")
            msg_alternative.attach(MIMEText(plain_text, "plain"))
            msg_alternative.attach(MIMEText(html_body, "html"))

            # Attach the alternative text content to the main message
            msg.attach(msg_alternative)

            # Attach PDF file
            with open(pdf_path, "rb") as f:
                attachment = MIMEApplication(f.read(), _subtype="pdf")
                attachment.add_header(
                    "Content-Disposition", f'attachment; filename="{filename}"'
                )
                msg.attach(attachment)

            # Send email
            await self._send_smtp_email(msg, recipient)
            logger.info("Successfully sent email to %s", recipient)
            return True

        except Exception as e:
            logger.error("Error sending email to %s: %s", recipient, e)
            return False

    async def _send_smtp_email(self, msg: MIMEMultipart, recipient: str) -> bool:
        """Send email via SMTP with settings from MongoDB."""
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

    def _create_email_body(
        self, edition: Edition, filename: str, firstname: str
    ) -> str:
        """
        Create HTML email body from template.

        Args:
            edition: Edition information
            filename: PDF filename
            recipient: Recipient email address

        Returns:
            HTML formatted email body
        """

        # Extract year from filename (first 4 characters)
        year = filename[:4] if len(filename) >= 4 else "unbekannt"

        # Email template with placeholders (using inline styles to avoid CSS brace conflicts)
        template = """
        <!DOCTYPE html>
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 0;">
            <div style="background-color: #d4edda; padding: 20px; text-align: center;">
                <h2 style="margin: 0; color: #333;">📈 Depot Butler - Neue Ausgabe {title} verfügbar</h2>
            </div>

            <div style="padding: 20px;">
                <p>Hallo {firstname},</p>

                <p>die neue Ausgabe <span style="color: #2c5aa0; font-weight: bold;">{title}</span> vom {publication_date} ist verfügbar und wurde automatisch für dich heruntergeladen.</p>

                <h3>📋 Details:</h3>
                <ul>
                    <li><strong>Titel:</strong> {title}</li>
                    <li><strong>Ausgabedatum:</strong> {publication_date}</li>
                    <li><strong>Dateiname:</strong> {filename}</li>
                </ul>

                <p>Die PDF-Datei findest du im Anhang dieser E-Mail.</p>

                <p>Viel Erfolg beim Trading!</p>
            </div>

            <div style="background-color: #f4f4f4; padding: 10px; text-align: center; font-size: 12px; color: #666;">
                <p style="margin: 0;">Diese E-Mail wurde automatisch von Depot Butler generiert.<br>
                Depot Butler - Automatisierte Finanzpublikationen</p>
            </div>
        </body>
        </html>
        """

        # Fill template with actual values
        return template.format(
            title=edition.title,
            publication_date=edition.publication_date,
            filename=filename,
            year=year,
            firstname=firstname,
        )

    async def send_success_notification(
        self, edition: Edition, onedrive_url: str
    ) -> bool:
        """
        Send success notification email (without attachment) to admin only.

        Args:
            edition: Edition information
            onedrive_url: URL to the file in OneDrive
            recipients: Optional list of recipients (ignored, uses admin_address)

        Returns:
            True if email sent successfully to admin
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

    async def send_warning_notification(
        self,
        warning_msg: str,
        title: str = "System Warning",
    ) -> bool:
        """
        Send warning notification email to admin only.

        Args:
            warning_msg: Warning message
            title: Warning title

        Returns:
            True if email sent successfully to admin
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

    async def _send_success_email(
        self, edition: Edition, onedrive_url: str, recipient: str
    ) -> bool:
        """Send success notification to single recipient."""
        try:
            # Use EXACT same structure as working PDF email
            msg = MIMEMultipart("alternative")

            firstname = recipient.split("@")[0].split(".")[0].capitalize()

            # Check if onedrive_url is HTML summary (consolidated notification)
            is_html_summary = onedrive_url.startswith("<")

            # Email headers (exactly like PDF email)
            msg["From"] = self.mail_settings.username
            msg["To"] = recipient

            if is_html_summary:
                msg["Subject"] = "Depot Butler - Daily Report"
            else:
                msg["Subject"] = (
                    f"Depot Butler - {edition.title} erfolgreich verarbeitet"
                )

            if is_html_summary:
                # For consolidated notifications, extract plain text from HTML summary
                # Simple HTML tag removal for plain text version
                import re

                plain_summary = re.sub(
                    r"<[^>]+>", "\n", onedrive_url
                )  # Replace tags with newlines
                plain_summary = re.sub(
                    r"\n\s*\n+", "\n\n", plain_summary
                )  # Clean up multiple newlines
                plain_summary = plain_summary.strip()

                plain_text = f"""Hallo {firstname},

{plain_summary}

Der nächste automatische Lauf ist für nächste Woche geplant.

Beste Grüße,
Depot Butler - Automatisierte Finanzpublikationen"""

                html_body = f"""<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 0;">
    <div style="background-color: #d4edda; padding: 20px; text-align: center;">
        <h2 style="margin: 0; color: #155724; font-weight: bold;">Depot Butler - Daily Report</h2>
    </div>

    <div style="padding: 20px;">
        <p>Hallo {firstname},</p>
        {onedrive_url}
        <p>Der nächste automatische Lauf ist für nächste Woche geplant.</p>
        <p>Beste Grüße,<br>Depot Butler - Automatisierte Finanzpublikationen</p>
    </div>
</body>
</html>"""
            else:
                # Single publication notification
                plain_text = f"""Hallo {firstname},

die neue Ausgabe {edition.title} vom {edition.publication_date} wurde erfolgreich verarbeitet.

Durchgeführte Aktionen:
- PDF heruntergeladen
- In OneDrive hochgeladen
- Per E-Mail versandt

Du kannst die Datei auch direkt in OneDrive öffnen:
{onedrive_url}

Der nächste automatische Lauf ist für nächste Woche geplant.

Beste Grüße,
Depot Butler - Automatisierte Finanzpublikationen"""

                html_body = f"""<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 0;">
    <div style="background-color: #d4edda; padding: 20px; text-align: center;">
        <h2 style="margin: 0; color: #155724; font-weight: bold;">Depot Butler - Verarbeitung erfolgreich</h2>
    </div>

    <div style="padding: 20px;">
        <p>Hallo {firstname},</p>

        <p>die neue Ausgabe <strong>{edition.title}</strong> vom {edition.publication_date} wurde erfolgreich verarbeitet.</p>

        <h3>Durchgeführte Aktionen:</h3>
        <ul>
            <li>PDF heruntergeladen</li>
            <li>In OneDrive hochgeladen</li>
            <li>Per E-Mail versandt</li>
        </ul>

        <p>Du kannst die Datei auch direkt in OneDrive öffnen:</p>
        <p><a href="{onedrive_url}" style="color: #007bff; text-decoration: none;">In OneDrive öffnen</a></p>

        <p>Der nächste automatische Lauf ist für nächste Woche geplant.</p>

        <p>Beste Grüße,<br>Depot Butler - Automatisierte Finanzpublikationen</p>
    </div>
</body>
</html>"""

            # Attach both versions EXACTLY like PDF email does
            msg.attach(MIMEText(plain_text, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            await self._send_smtp_email(msg, recipient)
            return True

        except Exception as e:
            logger.error("Error sending success email to %s: %s", recipient, e)
            return False

    async def _send_warning_email(
        self, warning_msg: str, title: str, recipient: str
    ) -> bool:
        """Send warning notification to single recipient."""
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = self.mail_settings.username
            msg["To"] = recipient
            msg["Subject"] = f"⚠️ Depot Butler - {title}"

            # Create warning notification body
            html_body = self._create_warning_body(warning_msg, recipient, title)

            # Create plain text version as fallback
            plain_text = f"""
Hello,

{title}:
{warning_msg}

Please update the configuration accordingly.

The next automatic attempt will be made at the regular time.

Depot Butler - Automated Financial Publications
            """.strip()

            # Attach both plain text and HTML versions
            msg.attach(MIMEText(plain_text, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            await self._send_smtp_email(msg, recipient)
            return True

        except Exception as e:
            logger.error("Error sending warning email to %s: %s", recipient, e)
            return False

    def _create_success_body(
        self, edition: Edition, onedrive_url: str, firstname: str
    ) -> str:
        """Create success notification email body."""

        template = """
        <!DOCTYPE html>
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 0;">
            <div style="background-color: #d4edda; padding: 20px; text-align: center;">
                <h2 style="margin: 0; color: #155724; font-weight: bold;">✅ Depot Butler - Verarbeitung erfolgreich</h2>
            </div>

            <div style="padding: 20px;">
                <p>Hallo {firstname},</p>

                <p>Die neue Ausgabe <strong>{title}</strong> vom {publication_date} wurde erfolgreich verarbeitet.</p>

                <h3>📋 Durchgeführte Aktionen:</h3>
                <ul>
                    <li>✅ PDF heruntergeladen</li>
                    <li>✅ In OneDrive hochgeladen</li>
                    <li>✅ Per E-Mail versandt</li>
                </ul>

                <p>Du kannst die Datei auch direkt in OneDrive öffnen:</p>
                <p><a href="{onedrive_url}" style="color: #007bff; text-decoration: none;">📁 In OneDrive öffnen</a></p>

                <p>Der nächste automatische Lauf ist für nächste Woche geplant.</p>
            </div>

            <div style="background-color: #f4f4f4; padding: 10px; text-align: center; font-size: 12px; color: #666;">
                <p style="margin: 0;">Depot Butler - Automatisierte Finanzpublikationen</p>
            </div>
        </body>
        </html>
        """

        return template.format(
            title=edition.title,
            publication_date=edition.publication_date,
            onedrive_url=onedrive_url,
            firstname=firstname,
        )

    def _create_warning_body(self, warning_msg: str, recipient: str, title: str) -> str:
        """Create warning notification email body."""
        template = """
        <!DOCTYPE html>
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 0;">
            <div style="background-color: #fff3cd; padding: 20px; text-align: center;">
                <h2 style="margin: 0; color: #856404; font-weight: bold;">⚠️  Depot Butler - {title}</h2>
            </div>

            <div style="padding: 20px;">
                <p>Hello {firstname},</p>

                <p>{title}:</p>

                <div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #ffc107; margin: 20px 0;">
                    {warning_msg}
                </div>

                <p>Please update the configuration accordingly.</p>

                <p>The next automatic attempt will be made at the regular time.</p>
            </div>

            <div style="background-color: #f4f4f4; padding: 10px; text-align: center; font-size: 12px; color: #666;">
                <p style="margin: 0;">Depot Butler - Automated Financial Publications</p>
            </div>
        </body>
        </html>
        """

        firstname = recipient.split("@")[0].split(".")[0].capitalize()

        return template.format(
            title=title,
            warning_msg=warning_msg,
            firstname=firstname,
        )

    async def send_error_notification(
        self,
        error_msg: str,
        edition_title: str | None = None,
        recipients: list[str] | None = None,
    ) -> bool:
        """
        Send error notification email to admin only.

        Args:
            error_msg: Error message
            edition_title: Optional edition title if available
            recipients: Optional list of recipients (ignored, uses admin_address)

        Returns:
            True if email sent successfully to admin
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
        self, error_msg: str, edition_title: str | None, recipient: str
    ) -> bool:
        """Send error notification to single recipient."""
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = self.mail_settings.username
            msg["To"] = recipient
            msg["Subject"] = "❌ Depot Butler - Fehler bei der Verarbeitung"

            # Create error notification body
            html_body = self._create_error_body(error_msg, recipient, edition_title)

            # Create plain text version as fallback
            title_info = (
                f"der Ausgabe '{edition_title}'"
                if edition_title
                else "einer neuen Ausgabe"
            )
            plain_text = f"""
Hallo,

bei der automatischen Verarbeitung {title_info} ist ein Fehler aufgetreten.

Fehlerdetails:
{error_msg}

Bitte prüfe die Konfiguration oder kontaktiere den Administrator.

Der nächste automatische Versuch wird zur regulären Zeit unternommen.

Depot Butler - Automatisierte Finanzpublikationen
            """.strip()

            # Attach both plain text and HTML versions
            msg.attach(MIMEText(plain_text, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            await self._send_smtp_email(msg, recipient)
            return True

        except Exception as e:
            logger.error("Error sending error email to %s: %s", recipient, e)
            return False

    def _create_error_body(
        self, error_msg: str, recipient: str, edition_title: str | None
    ) -> str:
        """Create error notification email body."""
        template = """
        <!DOCTYPE html>
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 0;">
            <div style="background-color: #f8d7da; padding: 20px; text-align: center;">
                <h2 style="margin: 0; color: #721c24; font-weight: bold;">❌ Depot Butler - Fehler aufgetreten</h2>
            </div>

            <div style="padding: 20px;">
                <p>Hallo {firstname},</p>

                <p>bei der automatischen Verarbeitung {title_info} ist ein Fehler aufgetreten.</p>

                <h3>🔍 Fehlerdetails:</h3>
                <div style="background-color: #f8f9fa; padding: 10px; border-left: 4px solid #dc3545;">
                    <strong>Fehlermeldung:</strong><br>
                    {error_msg}
                </div>

                <p>Bitte prüfe die Konfiguration oder kontaktiere den Administrator.</p>

                <p>Der nächste automatische Versuch wird zur regulären Zeit unternommen.</p>
            </div>

            <div style="background-color: #f4f4f4; padding: 10px; text-align: center; font-size: 12px; color: #666;">
                <p style="margin: 0;">Depot Butler - Automatisierte Finanzpublikationen</p>
            </div>
        </body>
        </html>
        """

        firstname = recipient.split("@")[0].split(".")[0].capitalize()
        title_info = (
            f"der Ausgabe '{edition_title}'" if edition_title else "einer neuen Ausgabe"
        )

        return template.format(
            title_info=title_info, firstname=firstname, error_msg=error_msg
        )
