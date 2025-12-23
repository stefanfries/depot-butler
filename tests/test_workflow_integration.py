"""Integration tests for the complete DepotButler workflow."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from depotbutler.models import Edition, UploadResult
from depotbutler.services.cookie_checking_service import CookieCheckingService
from depotbutler.services.notification_service import NotificationService
from depotbutler.services.publication_processing_service import (
    PublicationProcessingService,
)
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
        mock_publications = [
            {
                "publication_id": "megatrend-folger",
                "name": "Megatrend Folger",
                "subscription_id": "2477462",
                "subscription_number": "AM-01029205",
                "default_onedrive_folder": "Dokumente/Banken/DerAktionaer/Strategie_800-Prozent",
                "email_enabled": True,
                "onedrive_enabled": True,
                "organize_by_year": True,
                "active": True,
            }
        ]

        mock_recipients = [
            {"name": "Test", "email": "test@example.com", "onedrive_folder": None}
        ]

        with (
            patch(
                "depotbutler.workflow.close_mongodb_connection", new_callable=AsyncMock
            ),
            patch(
                "depotbutler.workflow.get_publications",
                new_callable=AsyncMock,
                return_value=mock_publications,
            ),
            patch(
                "depotbutler.services.publication_discovery_service.PublicationDiscoveryService.sync_publications_from_account",
                new_callable=AsyncMock,
                return_value={
                    "new_count": 0,
                    "updated_count": 0,
                    "deactivated_count": 0,
                },
            ),
            patch(
                "depotbutler.db.mongodb.get_recipients_for_publication",
                new_callable=AsyncMock,
                return_value=mock_recipients,
            ),
        ):
            # Inject mocked external services FIRST
            workflow.boersenmedien_client = mock_client
            workflow.onedrive_service = mock_onedrive
            workflow.email_service = mock_email

            # Now initialize internal services with the mocked dependencies
            workflow.cookie_checker = CookieCheckingService(workflow.email_service)
            workflow.notification_service = NotificationService(
                workflow.email_service, workflow.dry_run
            )
            workflow.publication_processor = PublicationProcessingService(
                boersenmedien_client=workflow.boersenmedien_client,
                onedrive_service=workflow.onedrive_service,
                email_service=workflow.email_service,
                edition_tracker=workflow.edition_tracker,
                settings=workflow.settings,
                dry_run=workflow.dry_run,
            )

            # Mock file operations
            with (
                patch("pathlib.Path.exists", return_value=True),
                patch("pathlib.Path.mkdir"),
                patch("os.path.exists", return_value=True),
                patch("os.remove"),
            ):
                # Run workflow
                result = await workflow.run_full_workflow()

                # Assertions - new multi-publication structure
                assert result["success"] is True
                assert result["publications_processed"] == 1
                assert result["publications_succeeded"] == 1
                assert result["publications_failed"] == 0
                assert result["publications_skipped"] == 0
                assert result["error"] is None
                assert len(result["results"]) == 1

                # Check first result
                pub_result = result["results"][0]
                assert pub_result.success is True
                assert pub_result.edition == mock_edition
                assert pub_result.already_processed is False
                assert pub_result.email_result is True  # Email sent successfully
                assert pub_result.upload_result.success is True

                # Verify all steps were called
                mock_client.login.assert_called_once()
                mock_client.get_latest_edition.assert_called_once()
                mock_client.download_edition.assert_called_once()
                mock_onedrive.authenticate.assert_called_once()
                mock_onedrive.upload_file.assert_called_once()
                mock_email.send_pdf_to_recipients.assert_called_once()
                # Consolidated notification sent instead of individual
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

        mock_email = AsyncMock()
        mock_email.send_warning_notification = AsyncMock(return_value=True)

        workflow.boersenmedien_client = mock_client
        workflow.email_service = mock_email

        # Mock edition tracker to return True (already processed)
        workflow.edition_tracker.is_already_processed = AsyncMock(return_value=True)

        mock_publications = [
            {
                "publication_id": "megatrend-folger",
                "name": "Megatrend Folger",
                "subscription_id": "2477462",
                "subscription_number": "AM-01029205",
                "default_onedrive_folder": "Dokumente/Banken/DerAktionaer/Strategie_800-Prozent",
                "email_enabled": True,
                "onedrive_enabled": True,
                "organize_by_year": True,
                "active": True,
            }
        ]
        with (
            patch(
                "depotbutler.workflow.close_mongodb_connection", new_callable=AsyncMock
            ),
            patch(
                "depotbutler.workflow.get_publications",
                new_callable=AsyncMock,
                return_value=mock_publications,
            ),
            patch(
                "depotbutler.services.publication_discovery_service.PublicationDiscoveryService.sync_publications_from_account",
                new_callable=AsyncMock,
                return_value={
                    "new_count": 0,
                    "updated_count": 0,
                    "deactivated_count": 0,
                },
            ),
            patch(
                "depotbutler.db.mongodb.get_recipients_for_publication",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            # Initialize services
            workflow.cookie_checker = CookieCheckingService(workflow.email_service)
            workflow.notification_service = NotificationService(
                workflow.email_service, workflow.dry_run
            )
            workflow.publication_processor = PublicationProcessingService(
                boersenmedien_client=workflow.boersenmedien_client,
                onedrive_service=workflow.onedrive_service,
                email_service=workflow.email_service,
                edition_tracker=workflow.edition_tracker,
                settings=workflow.settings,
                dry_run=workflow.dry_run,
            )

            result = await workflow.run_full_workflow()

            # Should succeed with one publication skipped
            assert result["success"] is True
            assert result["publications_processed"] == 1
            assert result["publications_skipped"] == 1
            assert result["publications_succeeded"] == 0
            assert len(result["results"]) == 1

            pub_result = result["results"][0]
            assert pub_result.already_processed is True
            assert pub_result.edition == mock_edition

            # Download should NOT be called
            mock_client.download_edition.assert_not_called()


@pytest.mark.asyncio
async def test_workflow_download_failure(mock_edition, mock_settings):
    """Test workflow handles download failures gracefully."""
    mock_publications = [
        {
            "publication_id": "megatrend-folger",
            "name": "Megatrend Folger",
            "subscription_id": "2477462",
            "subscription_number": "AM-01029205",
            "default_onedrive_folder": "Dokumente/Banken/DerAktionaer/Strategie_800-Prozent",
            "email_enabled": True,
            "onedrive_enabled": True,
            "organize_by_year": True,
            "active": True,
        }
    ]
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
            patch(
                "depotbutler.workflow.get_publications",
                new_callable=AsyncMock,
                return_value=mock_publications,
            ),
            patch(
                "depotbutler.services.publication_discovery_service.PublicationDiscoveryService.sync_publications_from_account",
                new_callable=AsyncMock,
                return_value={
                    "new_count": 0,
                    "updated_count": 0,
                    "deactivated_count": 0,
                },
            ),
            patch(
                "depotbutler.db.mongodb.get_recipients_for_publication",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            # Initialize services
            workflow.cookie_checker = CookieCheckingService(workflow.email_service)
            workflow.notification_service = NotificationService(
                workflow.email_service, workflow.dry_run
            )
            workflow.publication_processor = PublicationProcessingService(
                boersenmedien_client=workflow.boersenmedien_client,
                onedrive_service=workflow.onedrive_service,
                email_service=workflow.email_service,
                edition_tracker=workflow.edition_tracker,
                settings=workflow.settings,
                dry_run=workflow.dry_run,
            )

            result = await workflow.run_full_workflow()

            # Should fail - one publication failed
            assert result["success"] is False
            assert result["publications_failed"] == 1
            assert len(result["results"]) == 1

            pub_result = result["results"][0]
            assert pub_result.success is False
            assert "Failed to download edition" in pub_result.error

            # Error notification should be sent (consolidated)
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

        mock_publications = [
            {
                "publication_id": "megatrend-folger",
                "name": "Megatrend Folger",
                "subscription_id": "2477462",
                "subscription_number": "AM-01029205",
                "default_onedrive_folder": "Dokumente/Banken/DerAktionaer/Strategie_800-Prozent",
                "email_enabled": True,
                "onedrive_enabled": True,
                "organize_by_year": True,
                "active": True,
            }
        ]
        with (
            patch(
                "depotbutler.workflow.close_mongodb_connection", new_callable=AsyncMock
            ),
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.mkdir"),
            patch("os.path.exists", return_value=True),
            patch("os.remove"),
            patch(
                "depotbutler.workflow.get_publications",
                new_callable=AsyncMock,
                return_value=mock_publications,
            ),
            patch(
                "depotbutler.services.publication_discovery_service.PublicationDiscoveryService.sync_publications_from_account",
                new_callable=AsyncMock,
                return_value={
                    "new_count": 0,
                    "updated_count": 0,
                    "deactivated_count": 0,
                },
            ),
            patch(
                "depotbutler.db.mongodb.get_recipients_for_publication",
                new_callable=AsyncMock,
                return_value=[{"name": "Test", "email": "test@example.com"}],
            ),
        ):
            # Initialize services
            workflow.cookie_checker = CookieCheckingService(workflow.email_service)
            workflow.notification_service = NotificationService(
                workflow.email_service, workflow.dry_run
            )
            workflow.publication_processor = PublicationProcessingService(
                boersenmedien_client=workflow.boersenmedien_client,
                onedrive_service=workflow.onedrive_service,
                email_service=workflow.email_service,
                edition_tracker=workflow.edition_tracker,
                settings=workflow.settings,
                dry_run=workflow.dry_run,
            )

            result = await workflow.run_full_workflow()

            # Should fail - publication failed due to upload
            assert result["success"] is False
            assert result["publications_failed"] == 1
            assert len(result["results"]) == 1

            pub_result = result["results"][0]
            assert pub_result.success is False
            assert "Upload failed" in pub_result.error

            # Email should still be sent, but consolidated error notification too
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

        mock_publications = [
            {
                "publication_id": "megatrend-folger",
                "name": "Megatrend Folger",
                "subscription_id": "2477462",
                "subscription_number": "AM-01029205",
                "default_onedrive_folder": "Dokumente/Banken/DerAktionaer/Strategie_800-Prozent",
                "email_enabled": True,
                "onedrive_enabled": True,
                "organize_by_year": True,
                "active": True,
            }
        ]
        with (
            patch(
                "depotbutler.workflow.close_mongodb_connection", new_callable=AsyncMock
            ),
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.mkdir"),
            patch("os.path.exists", return_value=True),
            patch("os.remove"),
            patch(
                "depotbutler.workflow.get_publications",
                new_callable=AsyncMock,
                return_value=mock_publications,
            ),
            patch(
                "depotbutler.services.publication_discovery_service.PublicationDiscoveryService.sync_publications_from_account",
                new_callable=AsyncMock,
                return_value={
                    "new_count": 0,
                    "updated_count": 0,
                    "deactivated_count": 0,
                },
            ),
            patch(
                "depotbutler.db.mongodb.get_recipients_for_publication",
                new_callable=AsyncMock,
                return_value=[{"name": "Test", "email": "test@example.com"}],
            ),
        ):
            # Initialize services
            workflow.cookie_checker = CookieCheckingService(workflow.email_service)
            workflow.notification_service = NotificationService(
                workflow.email_service, workflow.dry_run
            )
            workflow.publication_processor = PublicationProcessingService(
                boersenmedien_client=workflow.boersenmedien_client,
                onedrive_service=workflow.onedrive_service,
                email_service=workflow.email_service,
                edition_tracker=workflow.edition_tracker,
                settings=workflow.settings,
                dry_run=workflow.dry_run,
            )

            result = await workflow.run_full_workflow()

            # Should still succeed (email is not critical)
            assert result["success"] is True
            assert result["publications_succeeded"] == 1
            assert result["publications_failed"] == 0
            assert len(result["results"]) == 1

            pub_result = result["results"][0]
            assert pub_result.success is True
            assert pub_result.email_result is False  # Email failed
            assert pub_result.upload_result.success is True

            # OneDrive upload should still happen
            mock_onedrive.upload_file.assert_called_once()
            # Consolidated notification sent instead of individual
            mock_email.send_success_notification.assert_called_once()


@pytest.mark.asyncio
async def test_workflow_tracking_disabled(mock_edition, mock_settings):
    """Test workflow with tracking disabled."""
    mock_settings.tracking.enabled = False

    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow()

        # Verify dummy tracker is created
        assert hasattr(workflow.edition_tracker, "is_already_processed")
        assert workflow.edition_tracker.get_processed_count() == 0


@pytest.mark.asyncio
async def test_workflow_cookie_expiration_warning(mock_edition, mock_settings):
    """Test cookie expiration warning notifications."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow()

        mock_email = AsyncMock()
        workflow.email_service = mock_email

        # Initialize cookie checker
        workflow.cookie_checker = CookieCheckingService(workflow.email_service)

        # Mock MongoDB with expiring cookie
        mock_mongodb = AsyncMock()
        mock_mongodb.get_cookie_expiration_info = AsyncMock(
            return_value={
                "days_remaining": 2,
                "is_expired": False,
                "expires_at": "2025-12-15",
            }
        )
        mock_mongodb.get_app_config = AsyncMock(return_value=5)

        with patch(
            "depotbutler.services.cookie_checking_service.get_mongodb_service",
            new_callable=AsyncMock,
            return_value=mock_mongodb,
        ):
            await workflow.cookie_checker.check_and_notify_expiration()

            # Should send warning notification
            mock_email.send_warning_notification.assert_called_once()
            call_args = mock_email.send_warning_notification.call_args
            assert "2 days" in call_args[1]["warning_msg"]


@pytest.mark.asyncio
async def test_workflow_cookie_expired_notification(mock_edition, mock_settings):
    """Test cookie expired warning notifications."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow()

        mock_email = AsyncMock()
        workflow.email_service = mock_email

        # Initialize cookie checker
        workflow.cookie_checker = CookieCheckingService(workflow.email_service)

        # Mock MongoDB with expired cookie
        mock_mongodb = AsyncMock()
        mock_mongodb.get_cookie_expiration_info = AsyncMock(
            return_value={
                "days_remaining": -5,
                "is_expired": True,
                "expires_at": "2025-12-08",
            }
        )
        mock_mongodb.get_app_config = AsyncMock(return_value=5)

        with patch(
            "depotbutler.services.cookie_checking_service.get_mongodb_service",
            new_callable=AsyncMock,
            return_value=mock_mongodb,
        ):
            await workflow.cookie_checker.check_and_notify_expiration()

            # Should send warning notification (not error)
            mock_email.send_warning_notification.assert_called_once()
            call_args = mock_email.send_warning_notification.call_args
            assert "expired" in call_args[1]["warning_msg"].lower()


@pytest.mark.asyncio
async def test_workflow_cookie_check_no_info(mock_edition, mock_settings):
    """Test cookie expiration check with no info available."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow()

        mock_email = AsyncMock()
        workflow.email_service = mock_email

        # Initialize cookie checker
        workflow.cookie_checker = CookieCheckingService(workflow.email_service)

        # Mock MongoDB with no cookie info
        mock_mongodb = AsyncMock()
        mock_mongodb.get_cookie_expiration_info = AsyncMock(return_value=None)

        with patch(
            "depotbutler.services.cookie_checking_service.get_mongodb_service",
            return_value=mock_mongodb,
        ):
            await workflow.cookie_checker.check_and_notify_expiration()

            # Should not send any notification
            mock_email.send_warning_notification.assert_not_called()


@pytest.mark.asyncio
async def test_workflow_cookie_check_exception(mock_edition, mock_settings):
    """Test cookie expiration check handling exceptions."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow()

        mock_email = AsyncMock()
        workflow.email_service = mock_email

        # Initialize cookie checker
        workflow.cookie_checker = CookieCheckingService(workflow.email_service)

        # Mock MongoDB that raises exception
        mock_mongodb = AsyncMock()
        mock_mongodb.get_cookie_expiration_info = AsyncMock(
            side_effect=Exception("DB error")
        )

        with patch(
            "depotbutler.services.cookie_checking_service.get_mongodb_service",
            return_value=mock_mongodb,
        ):
            # Should not raise exception
            await workflow.cookie_checker.check_and_notify_expiration()


@pytest.mark.asyncio
async def test_workflow_get_edition_info_exception(mock_edition, mock_settings):
    """Test _get_edition_info handling exceptions."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow()

        mock_client = AsyncMock()
        mock_client.get_latest_edition = AsyncMock(
            side_effect=Exception("Connection error")
        )
        workflow.boersenmedien_client = mock_client
        workflow.current_publication_data = {
            "publication_id": "test-pub",
            "subscription_id": "123",
            "subscription_number": "TEST-001",
        }

        result = await workflow._get_latest_edition_info()
        assert result is None


@pytest.mark.asyncio
async def test_workflow_onedrive_disabled_publication(mock_edition, mock_settings):
    """Test workflow with OneDrive disabled for publication."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow()

        # Mock components
        mock_client = AsyncMock()
        mock_onedrive = AsyncMock()
        mock_email = AsyncMock()

        mock_client.get_latest_edition = AsyncMock(return_value=mock_edition)
        mock_client.get_publication_date = AsyncMock(return_value=mock_edition)
        mock_client.get_publication_date = AsyncMock(return_value=mock_edition)
        mock_client.download_edition = AsyncMock()

        workflow.boersenmedien_client = mock_client
        workflow.onedrive_service = mock_onedrive
        workflow.email_service = mock_email
        workflow.edition_tracker = AsyncMock()
        workflow.edition_tracker.is_already_processed = AsyncMock(return_value=False)
        workflow.edition_tracker.mark_as_processed = AsyncMock()

        # Mock publication with OneDrive disabled
        mock_publications = [
            {
                "publication_id": "test-pub",
                "name": "Test Publication",
                "subscription_id": "123",
                "subscription_number": "TEST-001",
                "default_onedrive_folder": "Test/Folder",
                "email_enabled": True,
                "onedrive_enabled": False,
                "organize_by_year": True,
                "active": True,
            }
        ]

        with (
            patch(
                "depotbutler.workflow.get_publications", return_value=mock_publications
            ),
            patch(
                "depotbutler.workflow.close_mongodb_connection", new_callable=AsyncMock
            ),
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.mkdir"),
            patch("os.path.exists", return_value=True),
            patch("os.remove"),
            patch(
                "depotbutler.services.publication_discovery_service.PublicationDiscoveryService.sync_publications_from_account",
                new_callable=AsyncMock,
                return_value={
                    "new_count": 0,
                    "updated_count": 0,
                    "deactivated_count": 0,
                },
            ),
            patch(
                "depotbutler.db.mongodb.get_recipients_for_publication",
                new_callable=AsyncMock,
                return_value=[{"name": "Test", "email": "test@example.com"}],
            ),
        ):
            # Initialize services
            workflow.cookie_checker = CookieCheckingService(workflow.email_service)
            workflow.notification_service = NotificationService(
                workflow.email_service, workflow.dry_run
            )
            workflow.publication_processor = PublicationProcessingService(
                boersenmedien_client=workflow.boersenmedien_client,
                onedrive_service=workflow.onedrive_service,
                email_service=workflow.email_service,
                edition_tracker=workflow.edition_tracker,
                settings=workflow.settings,
                dry_run=workflow.dry_run,
            )

            result = await workflow.run_full_workflow()

            # Should skip OneDrive upload
            assert result["success"] is True
            mock_onedrive.upload_file.assert_not_called()

            # Email should still be sent
            mock_email.send_pdf_to_recipients.assert_called_once()


@pytest.mark.asyncio
async def test_workflow_email_disabled_publication(mock_edition, mock_settings):
    """Test workflow with email disabled for publication."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow()

        # Mock components
        mock_client = AsyncMock()
        mock_onedrive = AsyncMock()
        mock_email = AsyncMock()

        mock_client.get_latest_edition = AsyncMock(return_value=mock_edition)
        mock_client.get_publication_date = AsyncMock(return_value=mock_edition)
        mock_client.download_edition = AsyncMock()
        mock_onedrive.upload_file = AsyncMock(
            return_value=UploadResult(
                success=True, file_url="https://onedrive.com/test.pdf", file_id="123"
            )
        )

        workflow.boersenmedien_client = mock_client
        workflow.onedrive_service = mock_onedrive
        workflow.email_service = mock_email
        workflow.edition_tracker = AsyncMock()
        workflow.edition_tracker.is_already_processed = AsyncMock(return_value=False)
        workflow.edition_tracker.mark_as_processed = AsyncMock()

        # Mock publication with email disabled
        mock_publications = [
            {
                "publication_id": "test-pub",
                "name": "Test Publication",
                "subscription_id": "123",
                "subscription_number": "TEST-001",
                "default_onedrive_folder": "Test/Folder",
                "email_enabled": False,
                "onedrive_enabled": True,
                "organize_by_year": True,
                "active": True,
            }
        ]

        with (
            patch(
                "depotbutler.workflow.get_publications", return_value=mock_publications
            ),
            patch(
                "depotbutler.workflow.close_mongodb_connection", new_callable=AsyncMock
            ),
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.mkdir"),
            patch("os.path.exists", return_value=True),
            patch("os.path.exists", return_value=True),
            patch("os.remove"),
            patch(
                "depotbutler.services.publication_discovery_service.PublicationDiscoveryService.sync_publications_from_account",
                new_callable=AsyncMock,
                return_value={
                    "new_count": 0,
                    "updated_count": 0,
                    "deactivated_count": 0,
                },
            ),
            patch(
                "depotbutler.db.mongodb.get_recipients_for_publication",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            # Initialize services
            workflow.cookie_checker = CookieCheckingService(workflow.email_service)
            workflow.notification_service = NotificationService(
                workflow.email_service, workflow.dry_run
            )
            workflow.publication_processor = PublicationProcessingService(
                boersenmedien_client=workflow.boersenmedien_client,
                onedrive_service=workflow.onedrive_service,
                email_service=workflow.email_service,
                edition_tracker=workflow.edition_tracker,
                settings=workflow.settings,
                dry_run=workflow.dry_run,
            )

            result = await workflow.run_full_workflow()

            # Should skip email sending
            assert result["success"] is True
            assert result["publications_succeeded"] == 1

            pub_result = result["results"][0]
            assert pub_result.success is True
            assert pub_result.email_result is None  # Email disabled

            mock_email.send_pdf_to_recipients.assert_not_called()

            # OneDrive should still upload
            mock_onedrive.upload_file.assert_called_once()
