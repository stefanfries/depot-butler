"""Tests for email service (mailer.py)."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from depotbutler.mailer import EmailService
from depotbutler.models import Edition


@pytest.fixture
def email_service():
    """Create EmailService instance with mocked settings."""
    with patch("depotbutler.mailer.Settings") as mock_settings:
        settings = MagicMock()
        settings.mail.server = "smtp.test.com"
        settings.mail.port = 587
        settings.mail.username = "test@example.com"
        settings.mail.password = MagicMock()
        settings.mail.password.get_secret_value.return_value = "test_password"
        settings.mail.admin_address = "admin@example.com"
        mock_settings.return_value = settings

        service = EmailService()
        return service


@pytest.fixture
def mock_edition():
    """Create mock Edition for testing."""
    return Edition(
        title="Test Edition 47/2025",
        publication_date="2025-11-23",
        details_url="https://example.com/details",
        download_url="https://example.com/download",
    )


@pytest.mark.asyncio
async def test_send_pdf_to_recipients_success(email_service, mock_edition, tmp_path):
    """Test successful PDF sending to multiple recipients."""
    # Create temporary PDF file
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(b"fake pdf content")

    # Mock recipients
    mock_recipients = [
        {"email": "user1@example.com", "first_name": "User1"},
        {"email": "user2@example.com", "first_name": "User2"},
    ]

    with (
        patch(
            "depotbutler.mailer.get_active_recipients",
            new_callable=AsyncMock,
            return_value=mock_recipients,
        ),
        patch(
            "depotbutler.mailer.update_recipient_stats", new_callable=AsyncMock
        ) as mock_update,
        patch.object(
            email_service, "_send_individual_email", new_callable=AsyncMock
        ) as mock_send,
    ):
        mock_send.return_value = True

        result = await email_service.send_pdf_to_recipients(str(pdf_file), mock_edition)

        assert result is True
        assert mock_send.call_count == 2
        assert mock_update.call_count == 2


@pytest.mark.asyncio
async def test_send_pdf_to_recipients_file_not_found(email_service, mock_edition):
    """Test handling of missing PDF file."""
    result = await email_service.send_pdf_to_recipients(
        "/nonexistent/file.pdf", mock_edition
    )

    assert result is False


@pytest.mark.asyncio
async def test_send_pdf_to_recipients_no_recipients(
    email_service, mock_edition, tmp_path
):
    """Test handling when no recipients are found."""
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(b"fake pdf content")

    with patch(
        "depotbutler.mailer.get_active_recipients",
        new_callable=AsyncMock,
        return_value=[],
    ):
        result = await email_service.send_pdf_to_recipients(str(pdf_file), mock_edition)

        # No recipients is not an error - should return True
        assert result is True


@pytest.mark.asyncio
async def test_send_pdf_to_recipients_partial_failure(
    email_service, mock_edition, tmp_path
):
    """Test handling when some emails fail to send."""
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(b"fake pdf content")

    mock_recipients = [
        {"email": "user1@example.com", "first_name": "User1"},
        {"email": "user2@example.com", "first_name": "User2"},
    ]

    with (
        patch(
            "depotbutler.mailer.get_active_recipients",
            new_callable=AsyncMock,
            return_value=mock_recipients,
        ),
        patch("depotbutler.mailer.update_recipient_stats", new_callable=AsyncMock),
        patch.object(
            email_service, "_send_individual_email", new_callable=AsyncMock
        ) as mock_send,
    ):
        # First email succeeds, second fails
        mock_send.side_effect = [True, False]

        result = await email_service.send_pdf_to_recipients(str(pdf_file), mock_edition)

        assert result is False


@pytest.mark.asyncio
async def test_send_individual_email_success(email_service, mock_edition, tmp_path):
    """Test sending individual email with PDF attachment."""
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(b"fake pdf content")

    with patch("depotbutler.mailer.smtplib.SMTP") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        result = await email_service._send_individual_email(
            str(pdf_file), mock_edition, "test@example.com", "TestUser"
        )

        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once()
        mock_server.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_send_individual_email_smtp_failure(
    email_service, mock_edition, tmp_path
):
    """Test handling of SMTP errors."""
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(b"fake pdf content")

    with patch("depotbutler.mailer.smtplib.SMTP") as mock_smtp:
        mock_smtp.return_value.__enter__.return_value.send_message.side_effect = (
            Exception("SMTP Error")
        )

        result = await email_service._send_individual_email(
            str(pdf_file), mock_edition, "test@example.com", "TestUser"
        )

        assert result is False


@pytest.mark.asyncio
async def test_send_success_notification(email_service, mock_edition):
    """Test sending success notification to admin."""
    with patch.object(
        email_service, "_send_success_email", new_callable=AsyncMock
    ) as mock_send:
        mock_send.return_value = True

        result = await email_service.send_success_notification(
            mock_edition, "https://onedrive.com/file"
        )

        assert result is True
        mock_send.assert_called_once()
        # Should send to admin address
        assert mock_send.call_args[0][2] == "admin@example.com"


@pytest.mark.asyncio
async def test_send_error_notification(email_service):
    """Test sending error notification to admin."""
    with patch.object(
        email_service, "_send_error_email", new_callable=AsyncMock
    ) as mock_send:
        mock_send.return_value = True

        result = await email_service.send_error_notification(
            "Test error", edition_title="Test Edition"
        )

        assert result is True
        mock_send.assert_called_once()
        # Should send to admin address
        assert mock_send.call_args[0][2] == "admin@example.com"


@pytest.mark.asyncio
async def test_create_email_body(email_service, mock_edition):
    """Test email body template creation."""
    body = email_service._create_email_body(mock_edition, "test.pdf", "TestUser")

    assert "Test Edition 47/2025" in body
    assert "2025-11-23" in body
    assert "test.pdf" in body
    assert "TestUser" in body
    assert "<!DOCTYPE html>" in body


@pytest.mark.asyncio
async def test_send_smtp_email_success(email_service):
    """Test SMTP email sending."""
    mock_msg = MagicMock()

    with patch("depotbutler.mailer.smtplib.SMTP") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        await email_service._send_smtp_email(mock_msg, "test@example.com")

        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("test@example.com", "test_password")
        mock_server.send_message.assert_called_once_with(mock_msg)


@pytest.mark.asyncio
async def test_send_smtp_email_connection_error(email_service):
    """Test SMTP connection error handling."""
    mock_msg = MagicMock()

    with patch("depotbutler.mailer.smtplib.SMTP") as mock_smtp:
        mock_smtp.side_effect = Exception("Connection failed")

        with pytest.raises(Exception, match="Connection failed"):
            await email_service._send_smtp_email(mock_msg, "test@example.com")
