"""Pytest fixtures for workflow testing with pre-configured services.

This module provides reusable fixtures that eliminate repetitive service
initialization across workflow tests. Fixtures automatically wire up all
required services with mocked dependencies.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from depotbutler.models import Edition, UploadResult
from depotbutler.services.cookie_checking_service import CookieCheckingService
from depotbutler.services.edition_tracking_service import EditionTrackingService
from depotbutler.services.notification_service import NotificationService
from depotbutler.services.publication_processing_service import (
    PublicationProcessingService,
)
from depotbutler.workflow import DepotButlerWorkflow


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
def mock_boersenmedien_client(mock_edition):
    """Mock HttpxBoersenmedienClient with common configurations."""
    client = AsyncMock()
    client.login = AsyncMock()
    client.discover_subscriptions = AsyncMock()
    client.get_latest_edition = AsyncMock(return_value=mock_edition)
    client.get_publication_date = AsyncMock(return_value=mock_edition)
    client.download_edition = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_onedrive_service():
    """Mock OneDriveService with common configurations."""
    service = AsyncMock()
    service.authenticate = AsyncMock(return_value=True)
    service.upload_file = AsyncMock(
        return_value=UploadResult(
            success=True,
            file_url="https://onedrive.com/test.pdf",
            file_id="test-file-123",
        )
    )
    service.close = AsyncMock()
    return service


@pytest.fixture
def mock_email_service():
    """Mock EmailService with common configurations."""
    service = AsyncMock()
    service.send_pdf_to_recipients = AsyncMock(return_value=True)
    service.send_success_notification = AsyncMock(return_value=True)
    service.send_warning_notification = AsyncMock(return_value=True)
    service.send_error_notification = AsyncMock(return_value=True)
    return service


@pytest.fixture
def mock_edition_tracker():
    """Mock EditionTrackingService with common configurations."""
    tracker = AsyncMock(spec=EditionTrackingService)
    tracker.is_already_processed = AsyncMock(return_value=False)
    tracker.mark_as_processed = AsyncMock()
    return tracker


@pytest.fixture
def mock_recipients():
    """Sample recipient data for testing."""
    return [
        {
            "name": "Test User",
            "email": "test@example.com",
            "publication_preferences": [],
        }
    ]


@pytest.fixture
def mock_publications():
    """Sample publication data for testing."""
    return [
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


@pytest.fixture
def workflow_with_services(
    mock_settings,
    mock_boersenmedien_client,
    mock_onedrive_service,
    mock_email_service,
    mock_edition_tracker,
):
    """Pre-wired workflow with all services initialized.

    This fixture eliminates the need to manually wire up services in every test.
    All external dependencies (client, onedrive, email) are mocked, and all
    internal services are properly initialized with those mocks.

    Usage:
        @pytest.mark.asyncio
        async def test_something(workflow_with_services):
            workflow = workflow_with_services
            # Services are already initialized - just test!
            result = await workflow.run_full_workflow()
            assert result["success"]

    Returns:
        DepotButlerWorkflow with all services initialized and mocked.
    """
    from unittest.mock import patch

    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow()

        # Inject mocked external services
        workflow.boersenmedien_client = mock_boersenmedien_client
        workflow.onedrive_service = mock_onedrive_service
        workflow.email_service = mock_email_service
        workflow.edition_tracker = mock_edition_tracker

        # Initialize internal services with mocked dependencies
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

        yield workflow


@pytest.fixture
def workflow_with_services_dry_run(
    mock_settings,
    mock_boersenmedien_client,
    mock_onedrive_service,
    mock_email_service,
    mock_edition_tracker,
):
    """Pre-wired workflow in dry-run mode.

    Same as workflow_with_services but with dry_run=True.
    Useful for testing dry-run behavior without side effects.

    Returns:
        DepotButlerWorkflow with dry_run=True and all services initialized.
    """
    from unittest.mock import patch

    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow(dry_run=True)

        # Inject mocked external services
        workflow.boersenmedien_client = mock_boersenmedien_client
        workflow.onedrive_service = mock_onedrive_service
        workflow.email_service = mock_email_service
        workflow.edition_tracker = mock_edition_tracker

        # Initialize internal services with mocked dependencies (dry_run=True)
        workflow.cookie_checker = CookieCheckingService(workflow.email_service)
        workflow.notification_service = NotificationService(
            workflow.email_service, dry_run=True
        )
        workflow.publication_processor = PublicationProcessingService(
            boersenmedien_client=workflow.boersenmedien_client,
            onedrive_service=workflow.onedrive_service,
            email_service=workflow.email_service,
            edition_tracker=workflow.edition_tracker,
            settings=workflow.settings,
            dry_run=True,
        )

        yield workflow
