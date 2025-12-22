"""Integration tests for multi-publication workflow scenarios."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from depotbutler.models import Edition, UploadResult
from depotbutler.services.cookie_checker import CookieChecker
from depotbutler.services.notification_service import NotificationService
from depotbutler.services.publication_processor import PublicationProcessor
from depotbutler.workflow import DepotButlerWorkflow


@pytest.fixture
def mock_settings():
    """Mock Settings for testing."""
    settings = MagicMock()
    settings.tracking.enabled = True
    settings.tracking.temp_dir = str(Path.cwd() / "data" / "tmp")
    settings.tracking.retention_days = 90
    settings.dry_run = False
    return settings


@pytest.fixture
def mock_edition_1():
    """Create first mock Edition object."""
    return Edition(
        title="Der Aktionär 47/2025",
        publication_date="2025-11-23",
        details_url="https://example.com/details1",
        download_url="https://example.com/download/test1.pdf",
    )


@pytest.fixture
def mock_edition_2():
    """Create second mock Edition object."""
    return Edition(
        title="Megatrend Folger 12/2025",
        publication_date="2025-12-14",
        details_url="https://example.com/details2",
        download_url="https://example.com/download/test2.pdf",
    )


@pytest.mark.asyncio
async def test_workflow_two_publications_both_succeed(
    mock_edition_1, mock_edition_2, mock_settings
):
    """Test workflow with 2 publications, both process successfully."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow()

        mock_client = AsyncMock()
        mock_client.login = AsyncMock()
        mock_client.discover_subscriptions = AsyncMock()
        mock_client.close = AsyncMock()

        # Mock get_latest_edition to return different editions based on publication
        def get_edition_side_effect(publication):
            if publication.id == "der-aktionaer-epaper":
                return mock_edition_1
            else:
                return mock_edition_2

        mock_client.get_latest_edition = AsyncMock(side_effect=get_edition_side_effect)

        # Mock get_publication_date to return the edition unchanged
        mock_client.get_publication_date = AsyncMock(side_effect=lambda ed: ed)
        mock_client.download_edition = AsyncMock()

        mock_onedrive = AsyncMock()
        mock_onedrive.authenticate = AsyncMock(return_value=True)
        mock_onedrive.upload_file = AsyncMock(
            return_value=UploadResult(
                success=True, file_url="https://onedrive.com/test.pdf"
            )
        )
        mock_onedrive.close = AsyncMock()

        mock_email = AsyncMock()
        mock_email.send_pdf_to_recipients = AsyncMock(return_value=True)
        mock_email.send_success_notification = AsyncMock(return_value=True)

        workflow.boersenmedien_client = mock_client
        workflow.onedrive_service = mock_onedrive
        workflow.email_service = mock_email
        workflow.edition_tracker.is_already_processed = AsyncMock(return_value=False)
        workflow.edition_tracker.mark_as_processed = AsyncMock()

        # Initialize services
        workflow.cookie_checker = CookieChecker(workflow.email_service)
        workflow.notification_service = NotificationService(
            workflow.email_service, workflow.dry_run
        )
        workflow.publication_processor = PublicationProcessor(
            workflow.boersenmedien_client,
            workflow.onedrive_service,
            workflow.email_service,
            workflow.edition_tracker,
            mock_settings,
            workflow.dry_run,
        )

        mock_publications = [
            {
                "publication_id": "der-aktionaer-epaper",
                "name": "Der Aktionär",
                "subscription_id": "123",
                "subscription_number": "DA-001",
                "default_onedrive_folder": "Test/Folder1",
                "email_enabled": True,
                "onedrive_enabled": True,
                "organize_by_year": True,
                "active": True,
            },
            {
                "publication_id": "megatrend-folger",
                "name": "Megatrend Folger",
                "subscription_id": "456",
                "subscription_number": "MF-002",
                "default_onedrive_folder": "Test/Folder2",
                "email_enabled": True,
                "onedrive_enabled": True,
                "organize_by_year": True,
                "active": True,
            },
        ]

        with (
            patch(
                "depotbutler.discovery.PublicationDiscoveryService.sync_publications_from_account",
                return_value={
                    "new_count": 0,
                    "updated_count": 0,
                    "deactivated_count": 0,
                },
            ),
            patch(
                "depotbutler.db.mongodb.get_recipients_for_publication", return_value=[]
            ),
            patch(
                "depotbutler.workflow.get_publications",
                new_callable=AsyncMock,
                return_value=mock_publications,
            ),
            patch(
                "depotbutler.workflow.close_mongodb_connection", new_callable=AsyncMock
            ),
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.mkdir"),
            patch("os.path.exists", return_value=True),
            patch("os.remove"),
        ):
            result = await workflow.run_full_workflow()

            # Assertions
            assert result["success"] is True
            assert result["publications_processed"] == 2
            assert result["publications_succeeded"] == 2
            assert result["publications_failed"] == 0
            assert result["publications_skipped"] == 0
            assert len(result["results"]) == 2

            # Check first publication
            pub1 = result["results"][0]
            assert pub1.success is True
            assert pub1.publication_id == "der-aktionaer-epaper"
            assert pub1.edition == mock_edition_1
            assert pub1.email_result is True
            assert pub1.upload_result.success is True

            # Check second publication
            pub2 = result["results"][1]
            assert pub2.success is True
            assert pub2.publication_id == "megatrend-folger"
            assert pub2.edition == mock_edition_2
            assert pub2.email_result is True
            assert pub2.upload_result.success is True

            # Verify all steps called for both publications
            assert mock_client.get_latest_edition.call_count == 2
            assert mock_client.download_edition.call_count == 2
            assert mock_onedrive.upload_file.call_count == 2
            assert mock_email.send_pdf_to_recipients.call_count == 2
            assert workflow.edition_tracker.mark_as_processed.call_count == 2


@pytest.mark.asyncio
async def test_workflow_two_publications_one_new_one_skipped(
    mock_edition_1, mock_edition_2, mock_settings
):
    """Test workflow with 2 publications: 1 new, 1 already processed."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow()

        mock_client = AsyncMock()
        mock_client.login = AsyncMock()
        mock_client.discover_subscriptions = AsyncMock()
        mock_client.close = AsyncMock()

        def get_edition_side_effect(publication):
            if publication.id == "der-aktionaer-epaper":
                return mock_edition_1
            else:
                return mock_edition_2

        mock_client.get_latest_edition = AsyncMock(side_effect=get_edition_side_effect)
        mock_client.get_publication_date = AsyncMock(side_effect=lambda ed: ed)
        mock_client.download_edition = AsyncMock()

        mock_onedrive = AsyncMock()
        mock_onedrive.authenticate = AsyncMock(return_value=True)
        mock_onedrive.upload_file = AsyncMock(
            return_value=UploadResult(
                success=True, file_url="https://onedrive.com/test.pdf"
            )
        )
        mock_onedrive.close = AsyncMock()

        mock_email = AsyncMock()
        mock_email.send_pdf_to_recipients = AsyncMock(return_value=True)
        mock_email.send_warning_notification = AsyncMock(return_value=True)

        workflow.boersenmedien_client = mock_client
        workflow.onedrive_service = mock_onedrive
        workflow.email_service = mock_email

        # First publication already processed, second is new
        def is_processed_side_effect(edition):
            return edition == mock_edition_1

        workflow.edition_tracker.is_already_processed = AsyncMock(
            side_effect=is_processed_side_effect
        )
        workflow.edition_tracker.mark_as_processed = AsyncMock()

        # Initialize services
        workflow.cookie_checker = CookieChecker(workflow.email_service)
        workflow.notification_service = NotificationService(
            workflow.email_service, workflow.dry_run
        )
        workflow.publication_processor = PublicationProcessor(
            workflow.boersenmedien_client,
            workflow.onedrive_service,
            workflow.email_service,
            workflow.edition_tracker,
            mock_settings,
            workflow.dry_run,
        )

        mock_publications = [
            {
                "publication_id": "der-aktionaer-epaper",
                "name": "Der Aktionär",
                "subscription_id": "123",
                "subscription_number": "DA-001",
                "default_onedrive_folder": "Test/Folder1",
                "email_enabled": True,
                "onedrive_enabled": True,
                "organize_by_year": True,
                "active": True,
            },
            {
                "publication_id": "megatrend-folger",
                "name": "Megatrend Folger",
                "subscription_id": "456",
                "subscription_number": "MF-002",
                "default_onedrive_folder": "Test/Folder2",
                "email_enabled": True,
                "onedrive_enabled": True,
                "organize_by_year": True,
                "active": True,
            },
        ]

        with (
            patch(
                "depotbutler.discovery.PublicationDiscoveryService.sync_publications_from_account",
                return_value={
                    "new_count": 0,
                    "updated_count": 0,
                    "deactivated_count": 0,
                },
            ),
            patch(
                "depotbutler.db.mongodb.get_recipients_for_publication", return_value=[]
            ),
            patch(
                "depotbutler.workflow.get_publications",
                new_callable=AsyncMock,
                return_value=mock_publications,
            ),
            patch(
                "depotbutler.workflow.close_mongodb_connection", new_callable=AsyncMock
            ),
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.mkdir"),
            patch("os.path.exists", return_value=True),
            patch("os.remove"),
        ):
            result = await workflow.run_full_workflow()

            # Assertions
            assert result["success"] is True
            assert result["publications_processed"] == 2
            assert result["publications_succeeded"] == 1
            assert result["publications_failed"] == 0
            assert result["publications_skipped"] == 1
            assert len(result["results"]) == 2

            # First publication should be skipped
            pub1 = result["results"][0]
            assert pub1.success is True
            assert pub1.already_processed is True
            assert pub1.publication_id == "der-aktionaer-epaper"

            # Second publication should succeed
            pub2 = result["results"][1]
            assert pub2.success is True
            assert pub2.already_processed is False
            assert pub2.publication_id == "megatrend-folger"
            assert pub2.email_result is True
            assert pub2.upload_result.success is True

            # Only second publication processed
            assert mock_client.download_edition.call_count == 1
            assert mock_onedrive.upload_file.call_count == 1
            assert workflow.edition_tracker.mark_as_processed.call_count == 1


@pytest.mark.asyncio
async def test_workflow_two_publications_one_succeeds_one_fails(
    mock_edition_1, mock_edition_2, mock_settings
):
    """Test workflow with 2 publications: 1 succeeds, 1 fails."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow()

        mock_client = AsyncMock()
        mock_client.login = AsyncMock()
        mock_client.discover_subscriptions = AsyncMock()
        mock_client.close = AsyncMock()

        # First publication succeeds, second fails to get edition
        def get_edition_side_effect(publication):
            if publication.id == "der-aktionaer-epaper":
                return mock_edition_1
            else:
                return None  # Simulates failure

        mock_client.get_latest_edition = AsyncMock(side_effect=get_edition_side_effect)
        mock_client.get_publication_date = AsyncMock(side_effect=lambda ed: ed)
        mock_client.download_edition = AsyncMock()

        mock_onedrive = AsyncMock()
        mock_onedrive.authenticate = AsyncMock(return_value=True)
        mock_onedrive.upload_file = AsyncMock(
            return_value=UploadResult(
                success=True, file_url="https://onedrive.com/test.pdf"
            )
        )
        mock_onedrive.close = AsyncMock()

        mock_email = AsyncMock()
        mock_email.send_pdf_to_recipients = AsyncMock(return_value=True)
        mock_email.send_warning_notification = AsyncMock(return_value=True)

        workflow.boersenmedien_client = mock_client
        workflow.onedrive_service = mock_onedrive
        workflow.email_service = mock_email
        workflow.edition_tracker.is_already_processed = AsyncMock(return_value=False)
        workflow.edition_tracker.mark_as_processed = AsyncMock()

        # Initialize services
        workflow.cookie_checker = CookieChecker(workflow.email_service)
        workflow.notification_service = NotificationService(
            workflow.email_service, workflow.dry_run
        )
        workflow.publication_processor = PublicationProcessor(
            workflow.boersenmedien_client,
            workflow.onedrive_service,
            workflow.email_service,
            workflow.edition_tracker,
            mock_settings,
            workflow.dry_run,
        )

        mock_publications = [
            {
                "publication_id": "der-aktionaer-epaper",
                "name": "Der Aktionär",
                "subscription_id": "123",
                "subscription_number": "DA-001",
                "default_onedrive_folder": "Test/Folder1",
                "email_enabled": True,
                "onedrive_enabled": True,
                "organize_by_year": True,
                "active": True,
            },
            {
                "publication_id": "megatrend-folger",
                "name": "Megatrend Folger",
                "subscription_id": "456",
                "subscription_number": "MF-002",
                "default_onedrive_folder": "Test/Folder2",
                "email_enabled": True,
                "onedrive_enabled": True,
                "organize_by_year": True,
                "active": True,
            },
        ]

        with (
            patch(
                "depotbutler.discovery.PublicationDiscoveryService.sync_publications_from_account",
                return_value={
                    "new_count": 0,
                    "updated_count": 0,
                    "deactivated_count": 0,
                },
            ),
            patch(
                "depotbutler.db.mongodb.get_recipients_for_publication", return_value=[]
            ),
            patch(
                "depotbutler.workflow.get_publications",
                new_callable=AsyncMock,
                return_value=mock_publications,
            ),
            patch(
                "depotbutler.workflow.close_mongodb_connection", new_callable=AsyncMock
            ),
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.mkdir"),
            patch("os.path.exists", return_value=True),
            patch("os.remove"),
        ):
            result = await workflow.run_full_workflow()

            # Workflow should fail because one publication failed
            assert result["success"] is False
            assert result["publications_processed"] == 2
            assert result["publications_succeeded"] == 1
            assert result["publications_failed"] == 1
            assert result["publications_skipped"] == 0
            assert len(result["results"]) == 2

            # First publication succeeds
            pub1 = result["results"][0]
            assert pub1.success is True
            assert pub1.publication_id == "der-aktionaer-epaper"
            assert pub1.email_result is True

            # Second publication fails
            pub2 = result["results"][1]
            assert pub2.success is False
            assert pub2.publication_id == "megatrend-folger"
            assert pub2.error == "Failed to get latest edition"

            # Only first publication fully processed
            assert mock_client.download_edition.call_count == 1
            assert mock_onedrive.upload_file.call_count == 1
            assert workflow.edition_tracker.mark_as_processed.call_count == 1


@pytest.mark.asyncio
async def test_workflow_no_active_publications(mock_settings):
    """Test workflow when there are no active publications."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow()

        mock_client = AsyncMock()
        mock_client.login = AsyncMock()
        mock_client.discover_subscriptions = AsyncMock()
        mock_client.close = AsyncMock()

        mock_email = AsyncMock()
        mock_email.send_warning_notification = AsyncMock(return_value=True)

        workflow.boersenmedien_client = mock_client
        workflow.email_service = mock_email

        # Initialize services
        workflow.cookie_checker = CookieChecker(workflow.email_service)
        workflow.notification_service = NotificationService(
            workflow.email_service, workflow.dry_run
        )

        # No active publications
        mock_publications = []

        with (
            patch(
                "depotbutler.discovery.PublicationDiscoveryService.sync_publications_from_account",
                return_value={
                    "new_count": 0,
                    "updated_count": 0,
                    "deactivated_count": 0,
                },
            ),
            patch(
                "depotbutler.workflow.get_publications",
                new_callable=AsyncMock,
                return_value=mock_publications,
            ),
            patch(
                "depotbutler.workflow.close_mongodb_connection", new_callable=AsyncMock
            ),
        ):
            result = await workflow.run_full_workflow()

            # Should return with error (no publications is a config issue)
            assert result["success"] is False
            assert result["publications_processed"] == 0
            assert result["publications_succeeded"] == 0
            assert result["publications_failed"] == 0
            assert result["publications_skipped"] == 0
            assert len(result["results"]) == 0
            assert result["error"] == "No active publications configured"

            # Should not attempt any downloads
            mock_client.get_latest_edition.assert_not_called()
            mock_client.download_edition.assert_not_called()
