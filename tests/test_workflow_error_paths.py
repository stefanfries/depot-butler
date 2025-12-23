"""Tests for workflow error paths and edge cases."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from depotbutler.exceptions import (
    AuthenticationError,
    ConfigurationError,
    TransientError,
)
from depotbutler.models import Edition, UploadResult
from depotbutler.services.notification_service import NotificationService
from depotbutler.workflow import DepotButlerWorkflow


@pytest.fixture
def mock_settings():
    """Mock Settings for testing."""
    settings = MagicMock()
    settings.tracking.enabled = True
    settings.tracking.temp_dir = str(Path.cwd() / "data" / "tmp")
    settings.tracking.retention_days = 90
    return settings


@pytest.fixture
def mock_edition():
    """Create mock Edition object."""
    return Edition(
        title="Test Edition 01/2025",
        publication_date="2025-12-14",
        details_url="https://example.com/details",
        download_url="https://example.com/download/test.pdf",
    )


@pytest.fixture
def mock_publication():
    """Create mock publication data."""
    return {
        "publication_id": "test-publication",
        "name": "Test Publication",
        "subscription_id": "123",
        "subscription_number": "TEST-001",
        "default_onedrive_folder": "Test/Folder",
        "email_enabled": True,
        "onedrive_enabled": True,
        "organize_by_year": True,
        "active": True,
    }


@pytest.mark.asyncio
async def test_workflow_authentication_error(mock_settings):
    """Test workflow handles AuthenticationError correctly."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow()

        mock_client = AsyncMock()
        mock_client.login = AsyncMock(side_effect=AuthenticationError("Cookie expired"))
        mock_client.close = AsyncMock()

        mock_email = AsyncMock()
        mock_email.send_error_notification = AsyncMock(return_value=True)

        # Mock services (they're None until __aenter__)
        mock_cookie_checker = AsyncMock()
        mock_cookie_checker.check_and_notify_expiration = AsyncMock()

        workflow.boersenmedien_client = mock_client
        workflow.email_service = mock_email
        workflow.cookie_checker = mock_cookie_checker

        with (
            patch(
                "depotbutler.workflow.get_publications",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "depotbutler.workflow.close_mongodb_connection", new_callable=AsyncMock
            ),
        ):
            result = await workflow.run_full_workflow()

            assert result["success"] is False
            assert "Authentication failed" in result["error"]
            mock_email.send_error_notification.assert_called_once()


@pytest.mark.asyncio
async def test_workflow_configuration_error(mock_settings):
    """Test workflow handles ConfigurationError correctly."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow()

        mock_client = AsyncMock()
        mock_client.login = AsyncMock(side_effect=ConfigurationError("Missing config"))
        mock_client.close = AsyncMock()

        mock_email = AsyncMock()
        mock_email.send_error_notification = AsyncMock(return_value=True)

        # Mock services
        mock_cookie_checker = AsyncMock()
        mock_cookie_checker.check_and_notify_expiration = AsyncMock()

        workflow.boersenmedien_client = mock_client
        workflow.email_service = mock_email
        workflow.cookie_checker = mock_cookie_checker

        with (
            patch(
                "depotbutler.workflow.get_publications",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "depotbutler.workflow.close_mongodb_connection", new_callable=AsyncMock
            ),
        ):
            result = await workflow.run_full_workflow()

            assert result["success"] is False
            assert "Configuration error" in result["error"]
            mock_email.send_error_notification.assert_called_once()


@pytest.mark.asyncio
async def test_workflow_transient_error(mock_settings):
    """Test workflow handles TransientError correctly."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow()

        mock_client = AsyncMock()
        mock_client.login = AsyncMock(side_effect=TransientError("Network timeout"))
        mock_client.close = AsyncMock()

        mock_email = AsyncMock()
        mock_email.send_error_notification = AsyncMock(return_value=True)

        # Mock services
        mock_cookie_checker = AsyncMock()
        mock_cookie_checker.check_and_notify_expiration = AsyncMock()

        workflow.boersenmedien_client = mock_client
        workflow.email_service = mock_email
        workflow.cookie_checker = mock_cookie_checker

        with (
            patch(
                "depotbutler.workflow.get_publications",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "depotbutler.workflow.close_mongodb_connection", new_callable=AsyncMock
            ),
        ):
            result = await workflow.run_full_workflow()

            assert result["success"] is False
            assert "Temporary failure" in result["error"]
            mock_email.send_error_notification.assert_called_once()


@pytest.mark.asyncio
async def test_workflow_generic_exception(mock_settings):
    """Test workflow handles generic exceptions correctly."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow()

        mock_client = AsyncMock()
        mock_client.login = AsyncMock(side_effect=RuntimeError("Unexpected error"))
        mock_client.close = AsyncMock()

        mock_email = AsyncMock()
        mock_email.send_error_notification = AsyncMock(return_value=True)

        # Mock services
        mock_cookie_checker = AsyncMock()
        mock_cookie_checker.check_and_notify_expiration = AsyncMock()

        workflow.boersenmedien_client = mock_client
        workflow.email_service = mock_email
        workflow.cookie_checker = mock_cookie_checker

        with (
            patch(
                "depotbutler.workflow.get_publications",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "depotbutler.workflow.close_mongodb_connection", new_callable=AsyncMock
            ),
        ):
            result = await workflow.run_full_workflow()

            assert result["success"] is False
            assert "Workflow failed" in result["error"]
            mock_email.send_error_notification.assert_called_once()


@pytest.mark.asyncio
async def test_publication_processing_unexpected_exception(
    mock_settings, mock_publication
):
    """Test handling of unexpected exception during publication processing."""
    mock_mongodb = AsyncMock()
    # get_app_config must return the default value directly (not a coroutine)
    mock_mongodb.get_app_config.return_value = True
    # Mock cookie expiration check to avoid unawaited coroutine warning
    mock_mongodb.get_cookie_expiration_info.return_value = None

    with (
        patch("depotbutler.workflow.Settings", return_value=mock_settings),
        patch(
            "depotbutler.workflow.get_mongodb_service",
            new_callable=AsyncMock,
            return_value=mock_mongodb,
        ),
    ):
        workflow = DepotButlerWorkflow()

        mock_client = AsyncMock()
        mock_client.login = AsyncMock()
        mock_client.discover_subscriptions = AsyncMock()
        mock_client.get_latest_edition = AsyncMock(
            side_effect=RuntimeError("Unexpected error")
        )
        mock_client.close = AsyncMock()

        mock_email = AsyncMock()
        mock_email.send_consolidated_notification = AsyncMock(return_value=True)

        mock_discovery = AsyncMock()
        mock_discovery.sync_publications_from_account = AsyncMock(
            return_value={
                "discovered_count": 0,
                "new_count": 0,
                "updated_count": 0,
                "errors": [],
            }
        )

        workflow.boersenmedien_client = mock_client
        workflow.email_service = mock_email
        workflow.edition_tracker.is_already_processed = AsyncMock(return_value=False)

        # Mock services (they're None until __aenter__)
        mock_cookie_checker = AsyncMock()
        mock_cookie_checker.check_and_notify_expiration = AsyncMock()

        mock_notification_service = AsyncMock()
        mock_notification_service.send_consolidated_notification = AsyncMock()

        from depotbutler.services.publication_processing_service import (
            PublicationResult,
        )

        mock_publication_processor = AsyncMock()
        mock_publication_processor.process_publication = AsyncMock(
            return_value=PublicationResult(
                publication_id="test-publication",
                publication_name="Test Publication",
                success=False,
                error="Unexpected error",
            )
        )

        workflow.cookie_checker = mock_cookie_checker
        workflow.notification_service = mock_notification_service
        workflow.publication_processor = mock_publication_processor

        with (
            patch(
                "depotbutler.workflow.get_publications",
                new_callable=AsyncMock,
                return_value=[mock_publication],
            ),
            patch(
                "depotbutler.workflow.close_mongodb_connection", new_callable=AsyncMock
            ),
            patch(
                "depotbutler.services.publication_discovery_service.PublicationDiscoveryService",
                return_value=mock_discovery,
            ),
        ):
            result = await workflow.run_full_workflow()

            # When publication processing fails, workflow reports success=False
            assert result["success"] is False
            assert result["publications_failed"] == 1
            assert len(result["results"]) == 1
            assert result["results"][0].success is False
            assert "Unexpected error" in result["results"][0].error


@pytest.mark.asyncio
async def test_tracking_disabled_via_mongodb(mock_settings):
    """Test workflow when tracking is disabled via MongoDB config."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow()

        async def get_app_config_disabled(key, default):
            return False if key == "tracking_enabled" else 90

        mock_mongodb = AsyncMock()
        mock_mongodb.get_app_config = AsyncMock(side_effect=get_app_config_disabled)

        with patch(
            "depotbutler.workflow.get_mongodb_service",
            new_callable=AsyncMock,
            return_value=mock_mongodb,
        ):
            async with workflow:
                # When disabled, workflow uses SyncDummyTracker
                assert workflow.edition_tracker is not None
                assert workflow.edition_tracker.__class__.__name__ == "SyncDummyTracker"


@pytest.mark.asyncio
async def test_tracking_enabled_via_mongodb(mock_settings):
    """Test workflow when tracking is enabled via MongoDB config."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow()

        async def get_app_config_enabled(key, default):
            return True if key == "tracking_enabled" else 60

        mock_mongodb = AsyncMock()
        mock_mongodb.get_app_config = AsyncMock(side_effect=get_app_config_enabled)

        with patch(
            "depotbutler.workflow.get_mongodb_service",
            new_callable=AsyncMock,
            return_value=mock_mongodb,
        ):
            async with workflow:
                assert workflow.edition_tracker is not None
                assert workflow.edition_tracker.retention_days == 60


@pytest.mark.asyncio
async def test_send_success_notification_in_dry_run(mock_settings, mock_edition):
    """Test success notification is skipped in dry-run mode."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow(dry_run=True)

        upload_result = UploadResult(
            success=True, file_url="https://onedrive.com/test.pdf"
        )

        mock_email = AsyncMock()
        workflow.email_service = mock_email
        workflow.notification_service = NotificationService(mock_email, dry_run=True)

        await workflow.notification_service.send_success_notification(
            mock_edition, upload_result
        )

        # Should not call email service in dry-run mode
        mock_email.send_success_notification.assert_not_called()


@pytest.mark.asyncio
async def test_send_success_notification_production(mock_settings, mock_edition):
    """Test success notification is sent in production mode."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow(dry_run=False)

        upload_result = UploadResult(
            success=True, file_url="https://onedrive.com/test.pdf"
        )

        mock_email = AsyncMock()
        mock_email.send_success_notification = AsyncMock(return_value=True)
        workflow.email_service = mock_email
        workflow.notification_service = NotificationService(mock_email, dry_run=False)

        await workflow.notification_service.send_success_notification(
            mock_edition, upload_result
        )

        mock_email.send_success_notification.assert_called_once()


@pytest.mark.asyncio
async def test_send_success_notification_fails(mock_settings, mock_edition):
    """Test handling of success notification failure."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow(dry_run=False)

        upload_result = UploadResult(
            success=True, file_url="https://onedrive.com/test.pdf"
        )

        mock_email = AsyncMock()
        mock_email.send_success_notification = AsyncMock(return_value=False)
        workflow.email_service = mock_email
        workflow.notification_service = NotificationService(mock_email, dry_run=False)

        # Should not raise exception
        await workflow.notification_service.send_success_notification(
            mock_edition, upload_result
        )

        mock_email.send_success_notification.assert_called_once()


@pytest.mark.asyncio
async def test_send_success_notification_exception(mock_settings, mock_edition):
    """Test handling of exception during success notification."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow(dry_run=False)

        upload_result = UploadResult(
            success=True, file_url="https://onedrive.com/test.pdf"
        )

        mock_email = AsyncMock()
        mock_email.send_success_notification = AsyncMock(
            side_effect=RuntimeError("Email failed")
        )
        workflow.email_service = mock_email
        workflow.notification_service = NotificationService(mock_email, dry_run=False)

        # Should not raise exception
        await workflow.notification_service.send_success_notification(
            mock_edition, upload_result
        )


@pytest.mark.asyncio
async def test_send_error_notification_in_dry_run(mock_settings, mock_edition):
    """Test error notification is skipped in dry-run mode."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow(dry_run=True)

        mock_email = AsyncMock()
        workflow.email_service = mock_email
        workflow.notification_service = NotificationService(mock_email, dry_run=True)

        await workflow.notification_service.send_error_notification(
            mock_edition, "Test error"
        )

        # Should not call email service in dry-run mode
        mock_email.send_error_notification.assert_not_called()


@pytest.mark.asyncio
async def test_send_error_notification_production(mock_settings, mock_edition):
    """Test error notification is sent in production mode."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow(dry_run=False)

        mock_email = AsyncMock()
        mock_email.send_error_notification = AsyncMock(return_value=True)
        workflow.email_service = mock_email
        workflow.notification_service = NotificationService(mock_email, dry_run=False)

        await workflow.notification_service.send_error_notification(
            mock_edition, "Test error"
        )

        mock_email.send_error_notification.assert_called_once()


@pytest.mark.asyncio
async def test_send_error_notification_no_edition(mock_settings):
    """Test error notification with no edition (None)."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow(dry_run=False)

        mock_email = AsyncMock()
        mock_email.send_error_notification = AsyncMock(return_value=True)
        workflow.email_service = mock_email
        workflow.notification_service = NotificationService(mock_email, dry_run=False)

        await workflow.notification_service.send_error_notification(None, "Test error")

        mock_email.send_error_notification.assert_called_once()
        call_args = mock_email.send_error_notification.call_args
        assert call_args[1]["edition_title"] is None


@pytest.mark.asyncio
async def test_send_error_notification_exception(mock_settings, mock_edition):
    """Test handling of exception during error notification."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow(dry_run=False)

        mock_email = AsyncMock()
        mock_email.send_error_notification = AsyncMock(
            side_effect=RuntimeError("Email failed")
        )
        workflow.email_service = mock_email
        workflow.notification_service = NotificationService(mock_email, dry_run=False)

        # Should not raise exception
        await workflow.notification_service.send_error_notification(
            mock_edition, "Test error"
        )


@pytest.mark.asyncio
async def test_consolidated_notification_exception(mock_settings):
    """Test handling of exception during consolidated notification."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow(dry_run=False)

        mock_email = AsyncMock()
        mock_email.send_consolidated_notification = AsyncMock(
            side_effect=RuntimeError("Email failed")
        )
        workflow.email_service = mock_email
        workflow.notification_service = NotificationService(mock_email, dry_run=False)

        # Should not raise exception
        await workflow.notification_service.send_consolidated_notification([])


@pytest.mark.asyncio
async def test_force_reprocess_latest_success(mock_settings, mock_edition):
    """Test force_reprocess_latest successfully reprocesses edition."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow()

        mock_client = AsyncMock()
        mock_client.login = AsyncMock()
        mock_client.discover_subscriptions = AsyncMock()
        mock_client.close = AsyncMock()
        workflow.boersenmedien_client = mock_client

        mock_email = AsyncMock()
        workflow.email_service = mock_email

        workflow.edition_tracker.force_reprocess = AsyncMock(return_value=True)

        with (
            patch(
                "depotbutler.workflow.get_publications",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "depotbutler.workflow.close_mongodb_connection", new_callable=AsyncMock
            ),
            patch.object(
                workflow,
                "_get_latest_edition_info",
                new_callable=AsyncMock,
                return_value=mock_edition,
            ),
            patch(
                "depotbutler.services.publication_discovery_service.PublicationDiscoveryService",
            ),
        ):
            result = await workflow.force_reprocess_latest()

            assert result["was_previously_processed"] is True
            workflow.edition_tracker.force_reprocess.assert_called_once()


@pytest.mark.asyncio
async def test_force_reprocess_latest_no_edition(mock_settings):
    """Test force_reprocess_latest when no edition is available."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow()

        with patch.object(
            workflow,
            "_get_latest_edition_info",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await workflow.force_reprocess_latest()

            assert result["success"] is False
            assert "Failed to get edition information" in result["error"]


@pytest.mark.asyncio
async def test_force_reprocess_latest_exception(mock_settings):
    """Test force_reprocess_latest handles exceptions."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow()

        with patch.object(
            workflow,
            "_get_latest_edition_info",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Test error"),
        ):
            result = await workflow.force_reprocess_latest()

            assert result["success"] is False
            assert "Test error" in result["error"]
