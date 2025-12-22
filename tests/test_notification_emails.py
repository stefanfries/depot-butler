"""
Tests for mailer notification emails (_send_success_email, _send_error_email, _send_warning_email).
These tests cover notification methods and HTML body generation for different email types.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from depotbutler.mailer import EmailService
from depotbutler.models import Edition


@pytest.fixture
def email_service():
    """Create EmailService instance with mocked settings."""
    with patch("depotbutler.mailer.service.Settings") as mock_settings:
        settings = MagicMock()
        settings.mail.server = "smtp.test.com"
        settings.mail.port = 587
        settings.mail.username = "test@example.com"
        settings.mail.password = MagicMock()
        settings.mail.password.get_secret_value.return_value = "test_password"
        settings.mail.admin_address = "admin@example.com"
        settings.mail.admin_emails = ["admin@example.com"]
        mock_settings.return_value = settings

        service = EmailService()
        yield service


@pytest.fixture
def mock_edition():
    """Create a mock Edition object."""
    return Edition(
        title="Test Edition 47/2025",
        details_url="https://example.com/details",
        download_url="https://example.com/download",
        publication_date="2025-11-23",
    )


def decode_mime_part(msg, part_type="text/plain"):
    """Helper to decode MIME message parts."""
    for part in msg.walk():
        if part.get_content_type() == part_type:
            payload = part.get_payload(decode=True)
            if payload:
                return payload.decode("utf-8")
    return ""


# ============================================================================
# Tests for _send_success_email
# ============================================================================


@pytest.mark.asyncio
async def test_send_success_email_single_publication(email_service, mock_edition):
    """Test sending success email for single publication."""
    with patch.object(
        email_service, "_send_smtp_email", new_callable=AsyncMock
    ) as mock_smtp:
        result = await email_service._send_success_email(
            edition=mock_edition,
            onedrive_url="https://onedrive.com/file123",
            recipient="user@example.com",
        )

        assert result is True
        mock_smtp.assert_called_once()

        msg = mock_smtp.call_args[0][0]
        assert (
            msg["Subject"]
            == "Depot Butler - Test Edition 47/2025 erfolgreich verarbeitet"
        )
        assert msg["To"] == "user@example.com"
        assert msg["From"] == "test@example.com"

        # Check content in decoded plain text
        plain_text = decode_mime_part(msg, "text/plain")
        assert "Hallo User" in plain_text
        assert "Test Edition 47/2025" in plain_text
        assert "https://onedrive.com/file123" in plain_text


@pytest.mark.asyncio
async def test_send_success_email_consolidated_report(email_service):
    """Test sending success email with consolidated HTML report."""
    # HTML summary MUST start with '<' to trigger consolidated logic
    html_summary = "<h3>Processed Publications</h3><ul><li>Publication 1</li></ul>"

    with patch.object(
        email_service, "_send_smtp_email", new_callable=AsyncMock
    ) as mock_smtp:
        mock_edition = Edition(
            title="Ignored",
            publication_date="2025-01-01",
            details_url="",
            download_url="",
        )

        result = await email_service._send_success_email(
            edition=mock_edition,
            onedrive_url=html_summary,
            recipient="user@example.com",
        )

        assert result is True
        msg = mock_smtp.call_args[0][0]
        assert msg["Subject"] == "Depot Butler - Daily Report"
        assert msg["To"] == "user@example.com"

        # Check consolidated content
        plain_text = decode_mime_part(msg, "text/plain")
        assert "Hallo User" in plain_text
        assert "Processed Publications" in plain_text


@pytest.mark.asyncio
async def test_send_success_email_smtp_failure(email_service, mock_edition):
    """Test success email when SMTP send fails."""
    with patch.object(
        email_service,
        "_send_smtp_email",
        new_callable=AsyncMock,
        side_effect=Exception("SMTP error"),
    ):
        result = await email_service._send_success_email(
            edition=mock_edition,
            onedrive_url="https://onedrive.com/file123",
            recipient="user@example.com",
        )

        assert result is False


@pytest.mark.asyncio
async def test_send_success_email_extracts_firstname(email_service, mock_edition):
    """Test that firstname is correctly extracted from email address."""
    with patch.object(
        email_service, "_send_smtp_email", new_callable=AsyncMock
    ) as mock_smtp:
        result = await email_service._send_success_email(
            edition=mock_edition,
            onedrive_url="https://onedrive.com/file123",
            recipient="john.doe@example.com",
        )

        assert result is True
        msg = mock_smtp.call_args[0][0]
        # Firstname should be capitalized (John from john.doe)
        plain_text = decode_mime_part(msg, "text/plain")
        assert "Hallo John" in plain_text


# ============================================================================
# Tests for _send_error_email
# ============================================================================


@pytest.mark.asyncio
async def test_send_error_email_with_edition_title(email_service):
    """Test sending error email with edition title."""
    with patch.object(
        email_service, "_send_smtp_email", new_callable=AsyncMock
    ) as mock_smtp:
        result = await email_service._send_error_email(
            error_msg="Download failed: Network timeout",
            edition_title="Test Edition 47/2025",
            recipient="admin@example.com",
        )

        assert result is True
        mock_smtp.assert_called_once()

        msg = mock_smtp.call_args[0][0]
        assert msg["Subject"] == "❌ Depot Butler - Fehler bei der Verarbeitung"
        assert msg["To"] == "admin@example.com"

        # Check error details in decoded text
        plain_text = decode_mime_part(msg, "text/plain")
        assert "Download failed: Network timeout" in plain_text
        assert "Test Edition 47/2025" in plain_text


@pytest.mark.asyncio
async def test_send_error_email_without_edition_title(email_service):
    """Test sending error email without edition title."""
    with patch.object(
        email_service, "_send_smtp_email", new_callable=AsyncMock
    ) as mock_smtp:
        result = await email_service._send_error_email(
            error_msg="Authentication failed",
            edition_title=None,
            recipient="admin@example.com",
        )

        assert result is True
        msg = mock_smtp.call_args[0][0]

        # Check error appears in decoded text
        plain_text = decode_mime_part(msg, "text/plain")
        assert "Authentication failed" in plain_text


@pytest.mark.asyncio
async def test_send_error_email_smtp_failure(email_service):
    """Test error email when SMTP send fails."""
    with patch.object(
        email_service,
        "_send_smtp_email",
        new_callable=AsyncMock,
        side_effect=Exception("SMTP error"),
    ):
        result = await email_service._send_error_email(
            error_msg="Test error",
            edition_title="Test Edition",
            recipient="admin@example.com",
        )

        assert result is False


# ============================================================================
# Tests for _send_warning_email
# ============================================================================


@pytest.mark.asyncio
async def test_send_warning_email_cookie_expiration(email_service):
    """Test sending cookie expiration warning email."""
    with patch.object(
        email_service, "_send_smtp_email", new_callable=AsyncMock
    ) as mock_smtp:
        result = await email_service._send_warning_email(
            warning_msg="Cookie expires in 3 days",
            title="Cookie Expiration Warning",
            recipient="admin@example.com",
        )

        assert result is True
        mock_smtp.assert_called_once()

        msg = mock_smtp.call_args[0][0]
        assert msg["Subject"] == "⚠️ Depot Butler - Cookie Expiration Warning"
        assert msg["To"] == "admin@example.com"

        # Check warning in decoded text
        plain_text = decode_mime_part(msg, "text/plain")
        assert "Cookie expires in 3 days" in plain_text


@pytest.mark.asyncio
async def test_send_warning_email_smtp_failure(email_service):
    """Test warning email when SMTP send fails."""
    with patch.object(
        email_service,
        "_send_smtp_email",
        new_callable=AsyncMock,
        side_effect=Exception("SMTP error"),
    ):
        result = await email_service._send_warning_email(
            warning_msg="Test warning",
            title="Test Warning",
            recipient="admin@example.com",
        )

        assert result is False


# ============================================================================
# Tests for HTML body generation methods
# ============================================================================


@pytest.mark.asyncio
async def test_create_success_body(email_service, mock_edition):
    """Test HTML success body generation."""
    # We can't directly call _create_success_body, so test via _send_success_email
    with patch.object(
        email_service, "_send_smtp_email", new_callable=AsyncMock
    ) as mock_smtp:
        await email_service._send_success_email(
            edition=mock_edition,
            onedrive_url="https://onedrive.com/file123",
            recipient="user@example.com",
        )

        msg = mock_smtp.call_args[0][0]
        html_text = decode_mime_part(msg, "text/html")

        # Check HTML structure
        assert "<!DOCTYPE html>" in html_text
        assert "Verarbeitung erfolgreich" in html_text
        assert "Test Edition 47/2025" in html_text
        assert "https://onedrive.com/file123" in html_text


@pytest.mark.asyncio
async def test_create_error_body_with_edition(email_service):
    """Test HTML error body generation with edition title."""
    with patch.object(
        email_service, "_send_smtp_email", new_callable=AsyncMock
    ) as mock_smtp:
        await email_service._send_error_email(
            error_msg="Download failed",
            edition_title="Test Edition",
            recipient="admin@example.com",
        )

        msg = mock_smtp.call_args[0][0]
        html_text = decode_mime_part(msg, "text/html")

        assert "<!DOCTYPE html>" in html_text
        assert "Fehler aufgetreten" in html_text
        assert "Download failed" in html_text
        assert "Test Edition" in html_text


@pytest.mark.asyncio
async def test_create_error_body_without_edition(email_service):
    """Test HTML error body generation without edition title."""
    with patch.object(
        email_service, "_send_smtp_email", new_callable=AsyncMock
    ) as mock_smtp:
        await email_service._send_error_email(
            error_msg="Authentication failed",
            edition_title=None,
            recipient="admin@example.com",
        )

        msg = mock_smtp.call_args[0][0]
        html_text = decode_mime_part(msg, "text/html")

        assert "<!DOCTYPE html>" in html_text
        assert "Fehler aufgetreten" in html_text
        assert "Authentication failed" in html_text


@pytest.mark.asyncio
async def test_create_warning_body(email_service):
    """Test HTML warning body generation."""
    with patch.object(
        email_service, "_send_smtp_email", new_callable=AsyncMock
    ) as mock_smtp:
        await email_service._send_warning_email(
            warning_msg="Cookie expires soon",
            title="Warning Title",
            recipient="admin@example.com",
        )

        msg = mock_smtp.call_args[0][0]
        html_text = decode_mime_part(msg, "text/html")

        assert "<!DOCTYPE html>" in html_text
        assert "Warning Title" in html_text
        assert "Cookie expires soon" in html_text


@pytest.mark.asyncio
async def test_create_warning_body_extracts_firstname(email_service):
    """Test that warning email extracts firstname from recipient."""
    with patch.object(
        email_service, "_send_smtp_email", new_callable=AsyncMock
    ) as mock_smtp:
        await email_service._send_warning_email(
            warning_msg="Test warning",
            title="Test",
            recipient="jane.smith@example.com",
        )

        msg = mock_smtp.call_args[0][0]
        plain_text = decode_mime_part(msg, "text/plain")
        assert "Hallo Jane" in plain_text


# ============================================================================
# Tests for admin email distribution
# ============================================================================


@pytest.mark.asyncio
async def test_send_error_notification_to_multiple_admins(email_service):
    """Test sending error notification to multiple administrators."""
    with (
        patch.object(
            email_service, "_send_smtp_email", new_callable=AsyncMock
        ) as mock_smtp,
        patch.object(
            email_service,
            "_get_admin_emails",
            new_callable=AsyncMock,
            return_value=["admin1@example.com", "admin2@example.com"],
        ),
    ):
        result = await email_service.send_error_notification(
            error_msg="Test error", edition_title="Test Edition"
        )

        assert result is True
        # Should send to both admins
        assert mock_smtp.call_count == 2


@pytest.mark.asyncio
async def test_send_error_notification_partial_admin_failure(email_service):
    """Test error notification when some admins fail."""
    call_count = 0

    async def smtp_side_effect(msg):
        nonlocal call_count
        call_count += 1
        return call_count == 1  # First succeeds, second fails

    with patch.object(
        email_service,
        "_send_smtp_email",
        new_callable=AsyncMock,
        side_effect=smtp_side_effect,
    ):
        email_service.mail_settings.admin_emails = [
            "admin1@example.com",
            "admin2@example.com",
        ]

        result = await email_service.send_error_notification(
            error_msg="Test error", edition_title="Test Edition"
        )

        # Should return False since not all succeeded
        assert result is False


@pytest.mark.asyncio
async def test_send_warning_notification_to_multiple_admins(email_service):
    """Test sending warning notification to multiple administrators."""
    with (
        patch.object(
            email_service, "_send_smtp_email", new_callable=AsyncMock
        ) as mock_smtp,
        patch.object(
            email_service,
            "_get_admin_emails",
            new_callable=AsyncMock,
            return_value=["admin1@example.com", "admin2@example.com"],
        ),
    ):
        result = await email_service.send_warning_notification(
            warning_msg="Test warning", title="Test Warning"
        )

        assert result is True
        assert mock_smtp.call_count == 2


@pytest.mark.asyncio
async def test_send_warning_notification_all_admins_fail(email_service):
    """Test warning notification when all admins fail."""
    with (
        patch.object(
            email_service,
            "_send_smtp_email",
            new_callable=AsyncMock,
            side_effect=Exception("SMTP error"),
        ),
        patch.object(
            email_service,
            "_get_admin_emails",
            new_callable=AsyncMock,
            return_value=["admin@example.com"],
        ),
    ):
        result = await email_service.send_warning_notification(
            warning_msg="Test warning", title="Test Warning"
        )

        assert result is False


# ============================================================================
# Edge case tests
# ============================================================================


@pytest.mark.asyncio
async def test_send_success_email_empty_onedrive_url(email_service, mock_edition):
    """Test success email with empty OneDrive URL."""
    with patch.object(
        email_service, "_send_smtp_email", new_callable=AsyncMock
    ) as mock_smtp:
        result = await email_service._send_success_email(
            edition=mock_edition, onedrive_url="", recipient="user@example.com"
        )

        assert result is True
        mock_smtp.assert_called_once()


@pytest.mark.asyncio
async def test_send_error_email_long_error_message(email_service):
    """Test error email with very long error message."""
    long_error = "Error: " + "x" * 1000

    with patch.object(
        email_service, "_send_smtp_email", new_callable=AsyncMock
    ) as mock_smtp:
        result = await email_service._send_error_email(
            error_msg=long_error,
            edition_title="Test Edition",
            recipient="admin@example.com",
        )

        assert result is True
        msg = mock_smtp.call_args[0][0]

        # Check that long error is in decoded text
        plain_text = decode_mime_part(msg, "text/plain")
        assert long_error in plain_text


@pytest.mark.asyncio
async def test_send_warning_email_special_characters(email_service):
    """Test warning email with special characters in message."""
    warning_with_special = "Warning: <script>alert('test')</script> & special chars äöü"

    with patch.object(
        email_service, "_send_smtp_email", new_callable=AsyncMock
    ) as mock_smtp:
        result = await email_service._send_warning_email(
            warning_msg=warning_with_special,
            title="Special Chars Test",
            recipient="admin@example.com",
        )

        assert result is True
        msg = mock_smtp.call_args[0][0]

        # Check special chars preserved in text
        plain_text = decode_mime_part(msg, "text/plain")
        assert "alert('test')" in plain_text
        assert "äöü" in plain_text


@pytest.mark.asyncio
async def test_send_success_email_recipient_with_complex_email(
    email_service, mock_edition
):
    """Test success email with complex email address format."""
    with patch.object(
        email_service, "_send_smtp_email", new_callable=AsyncMock
    ) as mock_smtp:
        result = await email_service._send_success_email(
            edition=mock_edition,
            onedrive_url="https://onedrive.com/file123",
            recipient="john.doe+test@sub.example.com",
        )

        assert result is True
        msg = mock_smtp.call_args[0][0]
        # Should extract 'john' as firstname
        plain_text = decode_mime_part(msg, "text/plain")
        assert "Hallo John" in plain_text
