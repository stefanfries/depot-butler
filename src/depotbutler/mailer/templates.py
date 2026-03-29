"""Email template generation for notifications."""

import re

from depotbutler.models import Edition


def create_success_email_body(
    edition: Edition, onedrive_url: str, firstname: str
) -> tuple[str, str]:
    """Create success notification email body.

    Args:
        edition: Edition information
        onedrive_url: URL to file or HTML summary for consolidated reports
        firstname: Recipient's first name

    Returns:
        Tuple of (plain_text, html_body)
    """
    # Check if onedrive_url is HTML summary (consolidated notification)
    is_html_summary = onedrive_url.startswith("<")

    if is_html_summary:
        # For consolidated notifications, extract plain text from HTML summary
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
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
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
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
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

    return plain_text, html_body


def create_warning_email_body(
    warning_msg: str, title: str, firstname: str
) -> tuple[str, str]:
    """Create warning notification email body.

    Args:
        warning_msg: Warning message
        title: Warning title
        firstname: Recipient's first name

    Returns:
        Tuple of (plain_text, html_body)
    """
    # Two rendering paths depending on whether warning_msg is an HTML fragment or plain text.
    # HTML fragments (consolidated daily reports) need a clean direct-embed template —
    # identical in structure to create_success_email_body — so mobile clients render reliably.
    # Plain-text warnings (e.g. cookie expiry) use the yellow actionable warning template.
    is_html_content = warning_msg.startswith("<")

    if is_html_content:
        # Strip HTML tags for the plain text alternative
        plain_warning = re.sub(r"<[^>]+>", "\n", warning_msg)
        plain_warning = re.sub(r"\n\s*\n+", "\n\n", plain_warning).strip()

        plain_text = f"""Hello {firstname},

{title}

{plain_warning}

The next automatic attempt will be made at the regular time.

Depot Butler - Automated Financial Publications"""

        html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 0;">
    <div style="background-color: #fff3cd; padding: 20px; text-align: center;">
        <h2 style="margin: 0; color: #856404; font-weight: bold;">ℹ️ Depot Butler - {title}</h2>
    </div>

    <div style="padding: 20px;">
        <p>Hello {firstname},</p>
        {warning_msg}
        <p>The next automatic attempt will be made at the regular time.</p>
    </div>
</body>
</html>"""

    else:
        plain_text = f"""Hallo {firstname},

{title}:
{warning_msg}

Please update the configuration accordingly.

The next automatic attempt will be made at the regular time.

Depot Butler - Automated Financial Publications"""

        html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 0;">
    <div style="background-color: #fff3cd; padding: 20px; text-align: center;">
        <h2 style="margin: 0; color: #856404; font-weight: bold;">⚠️ Depot Butler - {title}</h2>
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
</html>"""

    return plain_text, html_body


def create_error_email_body(
    error_msg: str, edition_title: str | None, firstname: str
) -> tuple[str, str]:
    """Create error notification email body.

    Args:
        error_msg: Error message
        edition_title: Edition title if available
        firstname: Recipient's first name

    Returns:
        Tuple of (plain_text, html_body)
    """
    title_info = (
        f"der Ausgabe '{edition_title}'" if edition_title else "einer neuen Ausgabe"
    )

    plain_text = f"""Hallo {firstname},

bei der automatischen Verarbeitung {title_info} ist ein Fehler aufgetreten.

Fehlerdetails:
{error_msg}

Bitte prüfe die Konfiguration oder kontaktiere den Administrator.

Der nächste automatische Versuch wird zur regulären Zeit unternommen.

Depot Butler - Automatisierte Finanzpublikationen"""

    html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
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
</html>"""

    return plain_text, html_body


def extract_firstname_from_email(email: str) -> str:
    """Extract firstname from email address.

    Args:
        email: Email address

    Returns:
        Capitalized first name extracted from email
    """
    return email.split("@")[0].split(".")[0].capitalize()
