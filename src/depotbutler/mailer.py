"""
Email service for sending PDF attachments and notifications.
Supports SMTP with attachments and templated messages.
"""

import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Optional

from depotbutler.models import Edition
from depotbutler.settings import Settings
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


class EmailService:
    """
    Email service for sending notifications and PDF attachments.
    """

    def __init__(self):
        self.settings = Settings()
        self.mail_settings = self.settings.mail

    async def send_pdf_to_recipients(
        self, pdf_path: str, edition: Edition, recipients: Optional[List[str]] = None
    ) -> bool:
        """
        Send PDF file as attachment to all recipients in the recipients list.

        Args:
            pdf_path: Path to the PDF file
            edition: Edition information for email content
            recipients: Optional list of recipients (uses settings.recipients if None)

        Returns:
            True if all emails sent successfully, False otherwise
        """
        try:
            if not Path(pdf_path).exists():
                logger.error(f"PDF file not found: {pdf_path}")
                return False

            # Use provided recipients or fall back to settings
            recipients_list = recipients or self.mail_settings.recipients
            if not recipients_list:
                logger.warning("No recipients configured")
                return True  # Not an error, just no one to send to

            success_count = 0

            for recipient in recipients_list:
                success = await self._send_individual_email(
                    pdf_path, edition, recipient
                )
                if success:
                    success_count += 1
                else:
                    logger.error(f"Failed to send email to {recipient}")

            logger.info(
                f"Successfully sent {success_count}/{len(recipients_list)} emails"
            )
            return success_count == len(recipients_list)

        except Exception as e:
            logger.error(f"Error sending PDF emails: {e}")
            return False

    async def _send_individual_email(
        self, pdf_path: str, edition: Edition, recipient: str
    ) -> bool:
        """Send email with PDF attachment to a single recipient."""
        try:
            # Create message with alternative subtype for better compatibility
            msg = MIMEMultipart("alternative")

            # Email headers
            filename = Path(pdf_path).name
            msg["From"] = self.mail_settings.username
            msg["To"] = recipient
            msg["Subject"] = f"Neue Ausgabe {edition.title} verfügbar"

            # Extract firstname from recipient email
            firstname = recipient.split("@")[0].split(".")[0].capitalize()

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

            # Attach both plain text and HTML versions
            msg.attach(MIMEText(plain_text, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            # Attach PDF file
            with open(pdf_path, "rb") as f:
                attachment = MIMEApplication(f.read(), _subtype="pdf")
                attachment.add_header(
                    "Content-Disposition", f'attachment; filename="{filename}"'
                )
                msg.attach(attachment)

            # Send email
            await self._send_smtp_email(msg, recipient)
            logger.info(f"Successfully sent email to {recipient}")
            return True

        except Exception as e:
            logger.error(f"Error sending email to {recipient}: {e}")
            return False

    async def _send_smtp_email(self, msg, recipient: str):
        """Send email via SMTP."""
        try:
            with smtplib.SMTP(
                self.mail_settings.server, self.mail_settings.port
            ) as server:
                server.starttls()  # Enable encryption
                server.login(
                    self.mail_settings.username,
                    self.mail_settings.password.get_secret_value(),
                )
                server.send_message(msg)

        except Exception as e:
            logger.error(f"SMTP error sending to {recipient}: {e}")
            raise

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
            # Send notification only to admin
            admin_email = self.mail_settings.admin_address
            success = await self._send_success_email(edition, onedrive_url, admin_email)

            if success:
                logger.info(f"Sent success notification to admin: {admin_email}")
            else:
                logger.warning(
                    f"Failed to send success notification to admin: {admin_email}"
                )

            return success

        except Exception as e:
            logger.error(f"Error sending success notification: {e}")
            return False

    async def _send_success_email(
        self, edition: Edition, onedrive_url: str, recipient: str
    ) -> bool:
        """Send success notification to single recipient."""
        try:
            # Use EXACT same structure as working PDF email
            msg = MIMEMultipart("alternative")

            firstname = recipient.split("@")[0].split(".")[0].capitalize()

            # Email headers (exactly like PDF email)
            msg["From"] = self.mail_settings.username
            msg["To"] = recipient
            msg["Subject"] = f"Depot Butler - {edition.title} erfolgreich verarbeitet"

            # Create plain text version (exactly like PDF email structure)
            plain_text = f"""Hallo {firstname},

die neue Ausgabe {edition.title} vom {edition.publication_date} wurde erfolgreich verarbeitet.

Durchgeführte Aktionen:
- PDF heruntergeladen
- In OneDrive hochgeladen  
- Per E-Mail versandt

Sie können die Datei auch direkt in OneDrive öffnen:
{onedrive_url}

Der nächste automatische Lauf ist für nächste Woche geplant.

Beste Grüße,
Depot Butler - Automatisierte Finanzpublikationen"""

            # Create HTML version (exactly like PDF email structure)
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
        
        <p>Sie können die Datei auch direkt in OneDrive öffnen:</p>
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
            logger.error(f"Error sending success email to {recipient}: {e}")
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
                
                <p>Sie können die Datei auch direkt in OneDrive öffnen:</p>
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

    async def send_error_notification(
        self,
        error_msg: str,
        edition_title: Optional[str] = None,
        recipients: Optional[List[str]] = None,
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
            # Send error notification only to admin
            admin_email = self.mail_settings.admin_address
            success = await self._send_error_email(
                error_msg, edition_title, admin_email
            )

            if success:
                logger.info(f"Sent error notification to admin: {admin_email}")
            else:
                logger.warning(
                    f"Failed to send error notification to admin: {admin_email}"
                )

            return success

        except Exception as e:
            logger.error(f"Error sending error notification: {e}")
            return False

    async def _send_error_email(
        self, error_msg: str, edition_title: Optional[str], recipient: str
    ) -> bool:
        """Send error notification to single recipient."""
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = self.mail_settings.username
            msg["To"] = recipient
            msg["Subject"] = "❌ Depot Butler - Fehler bei der Verarbeitung"

            # Create error notification body
            html_body = self._create_error_body(error_msg, edition_title)

            # Create plain text version as fallback
            title_info = (
                f"der Ausgabe '{edition_title}'"
                if edition_title
                else "einer neuen Ausgabe"
            )
            plain_text = f"""
Hallo,

Bei der automatischen Verarbeitung {title_info} ist ein Fehler aufgetreten.

Fehlerdetails:
{error_msg}

Bitte prüfen Sie die Konfiguration oder kontaktieren Sie den Administrator.

Der nächste automatische Versuch wird zur regulären Zeit unternommen.

Depot Butler - Automatisierte Finanzpublikationen
            """.strip()

            # Attach both plain text and HTML versions
            msg.attach(MIMEText(plain_text, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            await self._send_smtp_email(msg, recipient)
            return True

        except Exception as e:
            logger.error(f"Error sending error email to {recipient}: {e}")
            return False

    def _create_error_body(self, error_msg: str, edition_title: Optional[str]) -> str:
        """Create error notification email body."""
        template = """
        <!DOCTYPE html>
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 0;">
            <div style="background-color: #f8d7da; padding: 20px; text-align: center;">
                <h2 style="margin: 0; color: #721c24; font-weight: bold;">❌ Depot Butler - Fehler aufgetreten</h2>
            </div>
            
            <div style="padding: 20px;">
                <p>Hallo,</p>
                
                <p>Bei der automatischen Verarbeitung {title_info} ist ein Fehler aufgetreten.</p>
                
                <h3>🔍 Fehlerdetails:</h3>
                <div style="background-color: #f8f9fa; padding: 10px; border-left: 4px solid #dc3545;">
                    <strong>Fehlermeldung:</strong><br>
                    {error_msg}
                </div>
                
                <p>Bitte prüfen Sie die Konfiguration oder kontaktieren Sie den Administrator.</p>
                
                <p>Der nächste automatische Versuch wird zur regulären Zeit unternommen.</p>
            </div>
            
            <div style="background-color: #f4f4f4; padding: 10px; text-align: center; font-size: 12px; color: #666;">
                <p style="margin: 0;">Depot Butler - Automatisierte Finanzpublikationen</p>
            </div>
        </body>
        </html>
        """

        title_info = (
            f"der Ausgabe '{edition_title}'" if edition_title else "einer neuen Ausgabe"
        )

        return template.format(title_info=title_info, error_msg=error_msg)
