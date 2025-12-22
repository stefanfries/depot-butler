"""MIME message composition for emails."""

from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from depotbutler.mailer.templates import (
    create_error_email_body,
    create_success_email_body,
    create_warning_email_body,
    extract_firstname_from_email,
)
from depotbutler.models import Edition


def create_pdf_attachment_message(
    pdf_path: str,
    edition: Edition,
    recipient: str,
    firstname: str,
    sender_email: str,
) -> MIMEMultipart:
    """Create MIME message with PDF attachment.

    Args:
        pdf_path: Path to PDF file
        edition: Edition information
        recipient: Recipient email address
        firstname: Recipient's first name
        sender_email: Sender email address

    Returns:
        MIMEMultipart message ready to send
    """
    # Create message with mixed subtype for attachments
    msg = MIMEMultipart("mixed")

    # Email headers
    filename = Path(pdf_path).name
    msg["From"] = sender_email
    msg["To"] = recipient
    msg["Subject"] = f"Neue Ausgabe {edition.title} verfügbar"

    # Create email body from template
    html_body = _create_pdf_email_body(edition, filename, firstname)

    # Create plain text version as fallback
    plain_text = f"""Hallo {firstname},

die neue Ausgabe {edition.title} vom {edition.publication_date} ist verfügbar und wurde automatisch für dich heruntergeladen.

Details:
- Titel: {edition.title}
- Ausgabedatum: {edition.publication_date}
- Dateiname: {filename}

Die PDF-Datei findest du im Anhang dieser E-Mail.

Viel Erfolg beim Trading!

Diese E-Mail wurde automatisch von Depot Butler generiert.
Depot Butler - Automatisierte Finanzpublikationen"""

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

    return msg


def create_success_notification_message(
    edition: Edition,
    onedrive_url: str,
    recipient: str,
    firstname: str | None,
    sender_email: str,
) -> MIMEMultipart:
    """Create success notification MIME message.

    Args:
        edition: Edition information
        onedrive_url: URL to file or HTML summary for consolidated reports
        recipient: Recipient email address
        firstname: Recipient's first name (if None, extracts from email)
        sender_email: Sender email address

    Returns:
        MIMEMultipart message ready to send
    """
    msg = MIMEMultipart("alternative")

    # Use provided firstname or fallback to email extraction
    if firstname is None:
        firstname = extract_firstname_from_email(recipient)

    # Check if onedrive_url is HTML summary (consolidated notification)
    is_html_summary = onedrive_url.startswith("<")

    # Email headers
    msg["From"] = sender_email
    msg["To"] = recipient

    if is_html_summary:
        msg["Subject"] = "Depot Butler - Daily Report"
    else:
        msg["Subject"] = f"Depot Butler - {edition.title} erfolgreich verarbeitet"

    # Get email body from template
    plain_text, html_body = create_success_email_body(edition, onedrive_url, firstname)

    # Attach both versions
    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    return msg


def create_warning_notification_message(
    warning_msg: str,
    title: str,
    recipient: str,
    firstname: str | None,
    sender_email: str,
) -> MIMEMultipart:
    """Create warning notification MIME message.

    Args:
        warning_msg: Warning message
        title: Warning title
        recipient: Recipient email address
        firstname: Recipient's first name (if None, extracts from email)
        sender_email: Sender email address

    Returns:
        MIMEMultipart message ready to send
    """
    msg = MIMEMultipart("alternative")
    msg["From"] = sender_email
    msg["To"] = recipient
    msg["Subject"] = f"⚠️ Depot Butler - {title}"

    # Use provided firstname or fallback to email extraction
    if firstname is None:
        firstname = extract_firstname_from_email(recipient)

    # Get email body from template
    plain_text, html_body = create_warning_email_body(warning_msg, title, firstname)

    # Attach both versions
    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    return msg


def create_error_notification_message(
    error_msg: str,
    edition_title: str | None,
    recipient: str,
    firstname: str | None,
    sender_email: str,
) -> MIMEMultipart:
    """Create error notification MIME message.

    Args:
        error_msg: Error message
        edition_title: Edition title if available
        recipient: Recipient email address
        firstname: Recipient's first name (if None, extracts from email)
        sender_email: Sender email address

    Returns:
        MIMEMultipart message ready to send
    """
    msg = MIMEMultipart("alternative")
    msg["From"] = sender_email
    msg["To"] = recipient
    msg["Subject"] = "❌ Depot Butler - Fehler bei der Verarbeitung"

    # Use provided firstname or fallback to email extraction
    if firstname is None:
        firstname = extract_firstname_from_email(recipient)

    # Get email body from template
    plain_text, html_body = create_error_email_body(error_msg, edition_title, firstname)

    # Attach both versions
    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    return msg


def _create_pdf_email_body(edition: Edition, filename: str, firstname: str) -> str:
    """Create HTML email body for PDF attachment email.

    Args:
        edition: Edition information
        filename: PDF filename
        firstname: Recipient's first name

    Returns:
        HTML formatted email body
    """
    # Extract year from filename (first 4 characters)
    year = filename[:4] if len(filename) >= 4 else "unbekannt"

    template = """<!DOCTYPE html>
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
</html>"""

    return template.format(
        title=edition.title,
        publication_date=edition.publication_date,
        filename=filename,
        year=year,
        firstname=firstname,
    )
