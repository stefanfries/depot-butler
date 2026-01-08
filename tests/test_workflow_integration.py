"""Integration tests for the complete DepotButler workflow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from depotbutler.models import UploadResult
from depotbutler.services.cookie_checking_service import CookieCheckingService
from depotbutler.workflow import DepotButlerWorkflow
from tests.helpers.workflow_setup import (
    patch_discovery_service,
    patch_file_operations,
    patch_mongodb_operations,
)


@pytest.mark.asyncio
async def test_full_workflow_success(
    workflow_with_services, mock_publications, mock_recipients, mock_edition
):
    """Test successful execution of the complete workflow."""
    workflow = workflow_with_services

    with (
        patch("depotbutler.workflow.close_mongodb_connection", new_callable=AsyncMock),
        patch_mongodb_operations(mock_publications, mock_recipients),
        patch_discovery_service(),
        patch_file_operations(),
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
        workflow.boersenmedien_client.login.assert_called_once()
        workflow.boersenmedien_client.get_latest_edition.assert_called_once()
        workflow.boersenmedien_client.download_edition.assert_called_once()
        workflow.onedrive_service.authenticate.assert_called_once()
        # upload_file called once: archive upload skipped when uploading to default folder
        assert workflow.onedrive_service.upload_file.call_count == 1
        workflow.email_service.send_pdf_to_recipients.assert_called_once()
        workflow.edition_tracker.mark_as_processed.assert_called_once()


@pytest.mark.asyncio
async def test_workflow_already_processed(
    workflow_with_services, mock_publications, mock_edition
):
    """Test workflow skips already processed editions."""
    workflow = workflow_with_services

    # Mock edition tracker to return True (already processed)
    workflow.edition_tracker.is_already_processed = AsyncMock(return_value=True)

    with (
        patch("depotbutler.workflow.close_mongodb_connection", new_callable=AsyncMock),
        patch_mongodb_operations(mock_publications, []),
        patch_discovery_service(),
    ):
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
        workflow.boersenmedien_client.download_edition.assert_not_called()


@pytest.mark.asyncio
async def test_workflow_download_failure(
    workflow_with_services, mock_publications, mock_edition
):
    """Test workflow handles download failures gracefully."""
    workflow = workflow_with_services

    # Mock download to fail
    workflow.boersenmedien_client.download_edition = AsyncMock(
        side_effect=Exception("Download failed")
    )

    with (
        patch("depotbutler.workflow.close_mongodb_connection", new_callable=AsyncMock),
        patch("pathlib.Path.mkdir"),
        patch_mongodb_operations(mock_publications, []),
        patch_discovery_service(),
    ):
        result = await workflow.run_full_workflow()

        # Should fail - one publication failed
        assert result["success"] is False
        assert result["publications_failed"] == 1
        assert len(result["results"]) == 1

        pub_result = result["results"][0]
        assert pub_result.success is False
        assert "Failed to download edition" in pub_result.error

        # Error notification should be sent (consolidated)
        workflow.email_service.send_error_notification.assert_called_once()


@pytest.mark.asyncio
async def test_workflow_onedrive_upload_failure(
    workflow_with_services, mock_publications, mock_recipients
):
    """Test workflow handles OneDrive upload failures."""

    workflow = workflow_with_services

    # Mock OneDrive upload to fail
    workflow.onedrive_service.upload_file = AsyncMock(
        return_value=UploadResult(success=False, error="Upload failed", file_url=None)
    )

    with (
        patch("depotbutler.workflow.close_mongodb_connection", new_callable=AsyncMock),
        patch_file_operations(),
        patch_mongodb_operations(mock_publications, mock_recipients),
        patch_discovery_service(),
    ):
        result = await workflow.run_full_workflow()

        # Should fail - publication failed due to upload
        assert result["success"] is False
        assert result["publications_failed"] == 1
        assert len(result["results"]) == 1

        pub_result = result["results"][0]
        assert pub_result.success is False
        assert "Upload failed" in pub_result.error

        # Email should still be sent, but consolidated error notification too
        workflow.email_service.send_pdf_to_recipients.assert_called_once()
        workflow.email_service.send_error_notification.assert_called_once()


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
async def test_workflow_email_failure_continues(
    workflow_with_services, mock_publications, mock_recipients
):
    """Test workflow continues even if email sending fails."""

    workflow = workflow_with_services

    # Email sending fails
    workflow.email_service.send_pdf_to_recipients = AsyncMock(return_value=False)

    with (
        patch("depotbutler.workflow.close_mongodb_connection", new_callable=AsyncMock),
        patch_file_operations(),
        patch_mongodb_operations(mock_publications, mock_recipients),
        patch_discovery_service(),
    ):
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

        # OneDrive upload should still happen (archive upload skipped due to deduplication)
        assert workflow.onedrive_service.upload_file.call_count == 1
        # Consolidated notification sent instead of individual
        workflow.email_service.send_success_notification.assert_called_once()


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
async def test_workflow_onedrive_disabled_publication(
    workflow_with_services, mock_recipients
):
    """Test workflow with OneDrive disabled for publication."""
    from tests.helpers.workflow_setup import create_mock_publication

    workflow = workflow_with_services

    # Mock publication with OneDrive disabled
    mock_publications = [
        create_mock_publication(
            publication_id="test-pub",
            name="Test Publication",
            subscription_id="123",
            email_enabled=True,
            onedrive_enabled=False,
        )
    ]

    with (
        patch("depotbutler.workflow.close_mongodb_connection", new_callable=AsyncMock),
        patch_file_operations(),
        patch_mongodb_operations(mock_publications, mock_recipients),
        patch_discovery_service(),
    ):
        result = await workflow.run_full_workflow()

        # Should skip OneDrive upload
        assert result["success"] is True
        workflow.onedrive_service.upload_file.assert_not_called()

        # Email should still be sent
        workflow.email_service.send_pdf_to_recipients.assert_called_once()


@pytest.mark.asyncio
async def test_workflow_email_disabled_publication(workflow_with_services):
    """Test workflow with email disabled for publication."""
    from tests.helpers.workflow_setup import (
        create_mock_publication,
        create_mock_recipient,
    )

    workflow = workflow_with_services

    # Mock publication with email disabled
    mock_publications = [
        create_mock_publication(
            publication_id="test-pub",
            name="Test Publication",
            subscription_id="123",
            email_enabled=False,
            onedrive_enabled=True,
        )
    ]

    # Need recipients for OneDrive upload
    mock_recipients = [
        create_mock_recipient(
            email="user@example.com",
            publication_id="test-pub",
            upload_enabled=True,
        )
    ]

    with (
        patch("depotbutler.workflow.close_mongodb_connection", new_callable=AsyncMock),
        patch_file_operations(),
        patch_mongodb_operations(mock_publications, mock_recipients),
        patch_discovery_service(),
    ):
        result = await workflow.run_full_workflow()

        # Should skip email sending
        assert result["success"] is True
        assert result["publications_succeeded"] == 1

        pub_result = result["results"][0]
        assert pub_result.success is True
        assert pub_result.email_result is None  # Email disabled

        workflow.email_service.send_pdf_to_recipients.assert_not_called()

        # OneDrive should still upload (archive upload skipped due to deduplication)
        assert workflow.onedrive_service.upload_file.call_count == 1
