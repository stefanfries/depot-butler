"""Tests for workflow error paths and edge cases - refactored to use new infrastructure."""

from unittest.mock import AsyncMock, patch

import pytest

from depotbutler.exceptions import (
    AuthenticationError,
    ConfigurationError,
    TransientError,
)
from depotbutler.models import UploadResult
from depotbutler.services.notification_service import NotificationService
from depotbutler.workflow import DepotButlerWorkflow
from tests.helpers.workflow_setup import (
    create_mock_publication,
    patch_mongodb_operations,
)

# ============================================================================
# Error Handling Tests
# ============================================================================


@pytest.mark.asyncio
async def test_workflow_authentication_error(workflow_with_services):
    """Test workflow handles AuthenticationError correctly."""
    workflow = workflow_with_services
    workflow.boersenmedien_client.login.side_effect = AuthenticationError(
        "Cookie expired"
    )

    with patch_mongodb_operations(mock_publications=[], mock_recipients=[]):
        result = await workflow.run_full_workflow()

        assert result["success"] is False
        assert "Authentication failed" in result["error"]
        workflow.email_service.send_error_notification.assert_called_once()


@pytest.mark.asyncio
async def test_workflow_configuration_error(workflow_with_services):
    """Test workflow handles ConfigurationError correctly."""
    workflow = workflow_with_services
    workflow.boersenmedien_client.login.side_effect = ConfigurationError(
        "Missing config"
    )

    with patch_mongodb_operations(mock_publications=[], mock_recipients=[]):
        result = await workflow.run_full_workflow()

        assert result["success"] is False
        assert "Configuration error" in result["error"]
        workflow.email_service.send_error_notification.assert_called_once()


@pytest.mark.asyncio
async def test_workflow_transient_error(workflow_with_services):
    """Test workflow handles TransientError correctly."""
    workflow = workflow_with_services
    workflow.boersenmedien_client.login.side_effect = TransientError("Network timeout")

    with patch_mongodb_operations(mock_publications=[], mock_recipients=[]):
        result = await workflow.run_full_workflow()

        assert result["success"] is False
        assert "Temporary failure" in result["error"]
        workflow.email_service.send_error_notification.assert_called_once()


@pytest.mark.asyncio
async def test_workflow_generic_exception(workflow_with_services):
    """Test workflow handles generic exceptions correctly."""
    workflow = workflow_with_services
    workflow.boersenmedien_client.login.side_effect = Exception("Unexpected error")

    with patch_mongodb_operations(mock_publications=[], mock_recipients=[]):
        result = await workflow.run_full_workflow()

        assert result["success"] is False
        assert "Unexpected error" in result["error"]
        workflow.email_service.send_error_notification.assert_called_once()


@pytest.mark.asyncio
async def test_publication_processing_unexpected_exception(
    workflow_with_services, mock_edition
):
    """Test publication processing handles unexpected exceptions."""
    workflow = workflow_with_services

    # Make get_latest_edition raise an unexpected exception
    workflow.boersenmedien_client.get_latest_edition.side_effect = Exception(
        "Scraping failed"
    )

    mock_publication = create_mock_publication(
        publication_id="test-pub", name="Test Publication"
    )

    with (
        patch_mongodb_operations(
            mock_publications=[mock_publication], mock_recipients=[]
        ),
        patch(
            "depotbutler.services.publication_discovery_service.PublicationDiscoveryService.sync_publications_from_account",
            return_value={
                "new_count": 0,
                "updated_count": 0,
                "deactivated_count": 0,
                "errors": [],
                "discovered_count": 0,
            },
        ),
    ):
        result = await workflow.run_full_workflow()

        # Workflow continues despite publication failure
        assert result["success"] is False
        assert result["publications_processed"] == 1
        assert result["publications_failed"] == 1
        assert len(result["results"]) == 1

        pub_result = result["results"][0]
        assert pub_result.success is False
        assert "Scraping failed" in pub_result.error


# ============================================================================
# Tracking Configuration Tests
# ============================================================================


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


# ============================================================================
# Notification Tests
# ============================================================================


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
async def test_consolidated_notification_exception(mock_settings, mock_edition):
    """Test consolidated notification handles exceptions gracefully."""
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


# ============================================================================
# Force Reprocess Tests
# ============================================================================


@pytest.mark.asyncio
async def test_force_reprocess_success(workflow_with_services, mock_edition):
    """Test force reprocess flag bypasses tracking check."""
    workflow = workflow_with_services

    # Setup: Edition would normally be skipped
    workflow.edition_tracker.is_already_processed.return_value = True

    mock_publication = create_mock_publication(publication_id="test-pub")
    workflow.boersenmedien_client.get_latest_edition.return_value = mock_edition

    # Mock force_reprocess flag
    workflow._force_reprocess = True

    with (
        patch_mongodb_operations(
            mock_publications=[mock_publication], mock_recipients=[]
        ),
        patch(
            "depotbutler.services.publication_discovery_service.PublicationDiscoveryService.sync_publications_from_account",
            return_value={
                "new_count": 0,
                "updated_count": 0,
                "deactivated_count": 0,
                "errors": [],
                "discovered_count": 0,
            },
        ),
    ):
        result = await workflow.run_full_workflow()

        # Should process despite tracking check
        assert result["success"] is True
        assert result["publications_processed"] == 1


@pytest.mark.asyncio
async def test_force_reprocess_no_edition(workflow_with_services):
    """Test force reprocess when no edition found."""
    workflow = workflow_with_services
    workflow.boersenmedien_client.get_latest_edition.return_value = None
    workflow._force_reprocess = True

    mock_publication = create_mock_publication(publication_id="test-pub")

    with (
        patch_mongodb_operations(
            mock_publications=[mock_publication], mock_recipients=[]
        ),
        patch(
            "depotbutler.services.publication_discovery_service.PublicationDiscoveryService.sync_publications_from_account",
            return_value={
                "new_count": 0,
                "updated_count": 0,
                "deactivated_count": 0,
                "errors": [],
                "discovered_count": 0,
            },
        ),
    ):
        result = await workflow.run_full_workflow()

        assert result["success"] is False
        assert result["publications_failed"] == 1


@pytest.mark.asyncio
async def test_force_reprocess_exception(workflow_with_services):
    """Test force reprocess when exception occurs."""
    workflow = workflow_with_services
    workflow.boersenmedien_client.get_latest_edition.side_effect = Exception(
        "Scraping failed"
    )
    workflow._force_reprocess = True

    mock_publication = create_mock_publication(publication_id="test-pub")

    with (
        patch_mongodb_operations(
            mock_publications=[mock_publication], mock_recipients=[]
        ),
        patch(
            "depotbutler.services.publication_discovery_service.PublicationDiscoveryService.sync_publications_from_account",
            return_value={
                "new_count": 0,
                "updated_count": 0,
                "deactivated_count": 0,
                "errors": [],
                "discovered_count": 0,
            },
        ),
    ):
        result = await workflow.run_full_workflow()

        assert result["success"] is False
        assert result["publications_failed"] == 1
