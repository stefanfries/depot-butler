"""Integration tests for the complete DepotButler workflow."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from depotbutler.models import Edition, UploadResult
from depotbutler.workflow import DepotButlerWorkflow


@pytest.fixture
def mock_edition():
    """Create a mock Edition object."""
    return Edition(
        title="Der Aktionär 47/2025",
        publication_date="2025-11-23",
        details_url="https://example.com/details",
        download_url="https://example.com/download/test.pdf",
    )


@pytest.fixture
def mock_settings():
    """Mock Settings for testing."""
    settings = MagicMock()

    # Tracking settings
    settings.tracking.enabled = True
    settings.tracking.temp_dir = str(Path.cwd() / "data" / "tmp")
    settings.tracking.retention_days = 30

    # Mail settings
    settings.mail.server = "smtp.test.com"
    settings.mail.port = 587
    settings.mail.username = "test@example.com"
    settings.mail.password = MagicMock()
    settings.mail.password.get_secret_value.return_value = "test_password"
    settings.mail.admin_address = "admin@example.com"

    # MongoDB settings
    settings.mongodb.name = "test_db"
    settings.mongodb.connection_string = "mongodb://localhost:27017"

    return settings


@pytest.mark.asyncio
async def test_full_workflow_success(mock_edition, mock_settings):
    """Test successful execution of the complete workflow."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        # Create workflow instance
        workflow = DepotButlerWorkflow()

        # Mock edition tracker to return False (not processed)
        workflow.edition_tracker.is_already_processed = AsyncMock(return_value=False)
        workflow.edition_tracker.mark_as_processed = AsyncMock()

        # Mock all external dependencies
        mock_client = AsyncMock()
        mock_onedrive = AsyncMock()
        mock_email = AsyncMock()

        # Mock BrowserBoersenmedienClient
        mock_client.login = AsyncMock()
        mock_client.discover_subscriptions = AsyncMock()
        mock_client.get_latest_edition = AsyncMock(return_value=mock_edition)
        mock_client.get_publication_date = AsyncMock(return_value=mock_edition)
        mock_client.download_edition = AsyncMock()
        mock_client.close = AsyncMock()

        # Mock OneDriveService
        mock_onedrive.authenticate = AsyncMock(return_value=True)
        mock_onedrive.upload_file = AsyncMock(
            return_value=UploadResult(
                success=True,
                file_url="https://onedrive.com/test.pdf",
                file_id="test-file-123",
            )
        )
        mock_onedrive.close = AsyncMock()

        # Mock EmailService
        mock_email.send_pdf_to_recipients = AsyncMock(return_value=True)
        mock_email.send_success_notification = AsyncMock(return_value=True)

        # Mock MongoDB
        with patch(
            "depotbutler.workflow.close_mongodb_connection", new_callable=AsyncMock
        ):
            # Inject mocked services
            workflow.boersenmedien_client = mock_client
            workflow.onedrive_service = mock_onedrive
            workflow.email_service = mock_email

            # Mock file operations
            with (
                patch("pathlib.Path.exists", return_value=True),
                patch("pathlib.Path.mkdir"),
                patch("os.path.exists", return_value=True),
                patch("os.remove"),
            ):

                # Run workflow
                result = await workflow.run_full_workflow()

                # Assertions
                assert result["success"] is True
                assert result["edition"] == mock_edition
                assert result["already_processed"] is False
                assert result["error"] is None
                assert result["upload_result"].success is True

                # Verify all steps were called
                mock_client.login.assert_called_once()
                mock_client.get_latest_edition.assert_called_once()
                mock_client.download_edition.assert_called_once()
                mock_onedrive.authenticate.assert_called_once()
                mock_onedrive.upload_file.assert_called_once()
                mock_email.send_pdf_to_recipients.assert_called_once()
                mock_email.send_success_notification.assert_called_once()
                workflow.edition_tracker.mark_as_processed.assert_called_once()


@pytest.mark.asyncio
async def test_workflow_already_processed(mock_edition, mock_settings):
    """Test workflow skips already processed editions."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow()

        mock_client = AsyncMock()
        mock_client.login = AsyncMock()
        mock_client.discover_subscriptions = AsyncMock()
        mock_client.get_latest_edition = AsyncMock(return_value=mock_edition)
        mock_client.get_publication_date = AsyncMock(return_value=mock_edition)
        mock_client.close = AsyncMock()

        workflow.boersenmedien_client = mock_client

        # Mock edition tracker to return True (already processed)
        workflow.edition_tracker.is_already_processed = AsyncMock(return_value=True)

        with patch(
            "depotbutler.workflow.close_mongodb_connection", new_callable=AsyncMock
        ):
            result = await workflow.run_full_workflow()

            # Should succeed but mark as already processed
            assert result["success"] is True
            assert result["already_processed"] is True
            assert result["edition"] == mock_edition

            # Download should NOT be called
            mock_client.download_edition.assert_not_called()


@pytest.mark.asyncio
async def test_workflow_download_failure(mock_edition, mock_settings):
    """Test workflow handles download failures gracefully."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow()

        mock_client = AsyncMock()
        mock_client.login = AsyncMock()
        mock_client.discover_subscriptions = AsyncMock()
        mock_client.get_latest_edition = AsyncMock(return_value=mock_edition)
        mock_client.get_publication_date = AsyncMock(return_value=mock_edition)
        mock_client.download_edition = AsyncMock(
            side_effect=Exception("Download failed")
        )
        mock_client.close = AsyncMock()

        mock_email = AsyncMock()
        mock_email.send_error_notification = AsyncMock(return_value=True)

        workflow.boersenmedien_client = mock_client
        workflow.email_service = mock_email
        workflow.edition_tracker.is_already_processed = AsyncMock(return_value=False)

        with (
            patch(
                "depotbutler.workflow.close_mongodb_connection", new_callable=AsyncMock
            ),
            patch("pathlib.Path.mkdir"),
        ):

            result = await workflow.run_full_workflow()

            # Should fail
            assert result["success"] is False
            assert "Failed to download edition" in result["error"]

            # Error notification should be sent
            mock_email.send_error_notification.assert_called_once()


@pytest.mark.asyncio
async def test_workflow_onedrive_upload_failure(mock_edition, mock_settings):
    """Test workflow handles OneDrive upload failures."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow()

        mock_client = AsyncMock()
        mock_client.login = AsyncMock()
        mock_client.discover_subscriptions = AsyncMock()
        mock_client.get_latest_edition = AsyncMock(return_value=mock_edition)
        mock_client.get_publication_date = AsyncMock(return_value=mock_edition)
        mock_client.download_edition = AsyncMock()
        mock_client.close = AsyncMock()

        mock_onedrive = AsyncMock()
        mock_onedrive.authenticate = AsyncMock(return_value=True)
        mock_onedrive.upload_file = AsyncMock(
            return_value=UploadResult(
                success=False, error="Upload failed", file_url=None
            )
        )
        mock_onedrive.close = AsyncMock()

        mock_email = AsyncMock()
        mock_email.send_pdf_to_recipients = AsyncMock(return_value=True)
        mock_email.send_error_notification = AsyncMock(return_value=True)

        workflow.boersenmedien_client = mock_client
        workflow.onedrive_service = mock_onedrive
        workflow.email_service = mock_email
        workflow.edition_tracker.is_already_processed = AsyncMock(return_value=False)

        with (
            patch(
                "depotbutler.workflow.close_mongodb_connection", new_callable=AsyncMock
            ),
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.mkdir"),
            patch("os.path.exists", return_value=True),
            patch("os.remove"),
        ):

            result = await workflow.run_full_workflow()

            # Should fail
            assert result["success"] is False
            assert "Upload failed" in result["error"]

            # Email should still be sent, but error notification too
            mock_email.send_pdf_to_recipients.assert_called_once()
            mock_email.send_error_notification.assert_called_once()


@pytest.mark.asyncio
async def test_workflow_context_manager():
    """Test workflow context manager properly initializes and cleans up services."""
    with patch("depotbutler.workflow.Settings") as mock_settings_class:
        mock_settings = MagicMock()
        mock_settings.tracking.enabled = False
        mock_settings_class.return_value = mock_settings

        with patch(
            "depotbutler.workflow.close_mongodb_connection", new_callable=AsyncMock
        ) as mock_close_db:
            async with DepotButlerWorkflow() as workflow:
                # Services should be initialized
                assert workflow.boersenmedien_client is not None
                assert workflow.onedrive_service is not None
                assert workflow.email_service is not None

            # MongoDB connection should be closed after context exit
            mock_close_db.assert_called_once()


@pytest.mark.asyncio
async def test_workflow_email_failure_continues(mock_edition, mock_settings):
    """Test workflow continues even if email sending fails."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow()

        mock_client = AsyncMock()
        mock_client.login = AsyncMock()
        mock_client.discover_subscriptions = AsyncMock()
        mock_client.get_latest_edition = AsyncMock(return_value=mock_edition)
        mock_client.get_publication_date = AsyncMock(return_value=mock_edition)
        mock_client.download_edition = AsyncMock()
        mock_client.close = AsyncMock()

        mock_onedrive = AsyncMock()
        mock_onedrive.authenticate = AsyncMock(return_value=True)
        mock_onedrive.upload_file = AsyncMock(
            return_value=UploadResult(
                success=True, file_url="https://onedrive.com/test.pdf"
            )
        )
        mock_onedrive.close = AsyncMock()

        mock_email = AsyncMock()
        # Email sending fails
        mock_email.send_pdf_to_recipients = AsyncMock(return_value=False)
        mock_email.send_success_notification = AsyncMock(return_value=True)

        workflow.boersenmedien_client = mock_client
        workflow.onedrive_service = mock_onedrive
        workflow.email_service = mock_email
        workflow.edition_tracker.is_already_processed = AsyncMock(return_value=False)
        workflow.edition_tracker.mark_as_processed = AsyncMock()

        with (
            patch(
                "depotbutler.workflow.close_mongodb_connection", new_callable=AsyncMock
            ),
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.mkdir"),
            patch("os.path.exists", return_value=True),
            patch("os.remove"),
        ):

            result = await workflow.run_full_workflow()

            # Should still succeed (email is not critical)
            assert result["success"] is True
            assert result["upload_result"].success is True

            # OneDrive upload should still happen
            mock_onedrive.upload_file.assert_called_once()
            mock_email.send_success_notification.assert_called_once()
