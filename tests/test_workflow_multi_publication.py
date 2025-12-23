"""Integration tests for multi-publication workflow scenarios."""

import pytest

from depotbutler.models import Edition
from tests.helpers.workflow_setup import (
    create_mock_publication,
    patch_discovery_service,
    patch_file_operations,
    patch_mongodb_operations,
)


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
    workflow_with_services, mock_edition_1, mock_edition_2
):
    """Test workflow with 2 publications, both process successfully."""
    workflow = workflow_with_services

    # Define side_effect for edition switching based on publication ID
    def get_edition_side_effect(publication):
        # Publication is a PublicationConfig object with .id attribute
        if publication.id == "der-aktionaer-epaper":
            return mock_edition_1
        else:
            return mock_edition_2

    workflow.boersenmedien_client.get_latest_edition.side_effect = (
        get_edition_side_effect
    )
    # Make get_publication_date return the edition unchanged (passthrough)
    workflow.boersenmedien_client.get_publication_date.side_effect = lambda ed: ed

    mock_publications = [
        create_mock_publication(
            publication_id="der-aktionaer-epaper",
            name="Der Aktionär",
            subscription_id="123",
            subscription_number="DA-001",
        ),
        create_mock_publication(
            publication_id="megatrend-folger",
            name="Megatrend Folger",
            subscription_id="456",
            subscription_number="MF-002",
        ),
    ]

    with (
        patch_mongodb_operations(
            mock_publications=mock_publications, mock_recipients=[]
        ),
        patch_discovery_service(),
        patch_file_operations(),
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
        assert pub1.edition.title == mock_edition_1.title
        assert pub1.edition.publication_date == mock_edition_1.publication_date
        assert pub1.email_result is True
        assert pub1.upload_result.success is True

        # Check second publication
        pub2 = result["results"][1]
        assert pub2.success is True
        assert pub2.publication_id == "megatrend-folger"
        assert pub2.edition.title == mock_edition_2.title
        assert pub2.edition.publication_date == mock_edition_2.publication_date
        assert pub2.email_result is True
        assert pub2.upload_result.success is True

        # Verify all steps called for both publications
        assert workflow.boersenmedien_client.get_latest_edition.call_count == 2
        assert workflow.boersenmedien_client.download_edition.call_count == 2
        assert workflow.onedrive_service.upload_file.call_count == 2
        assert workflow.email_service.send_pdf_to_recipients.call_count == 2
        assert workflow.edition_tracker.mark_as_processed.call_count == 2


@pytest.mark.asyncio
async def test_workflow_two_publications_one_new_one_skipped(
    workflow_with_services, mock_edition_1, mock_edition_2
):
    """Test workflow with 2 publications: 1 new, 1 already processed."""
    workflow = workflow_with_services

    # Define side_effect for edition switching
    def get_edition_side_effect(publication):
        if publication.id == "der-aktionaer-epaper":
            return mock_edition_1
        else:
            return mock_edition_2

    workflow.boersenmedien_client.get_latest_edition.side_effect = (
        get_edition_side_effect
    )
    workflow.boersenmedien_client.get_publication_date.side_effect = lambda ed: ed

    # Mock tracker: first publication already processed, second is new
    workflow.edition_tracker.is_already_processed.side_effect = (
        lambda ed: ed == mock_edition_1
    )

    mock_publications = [
        create_mock_publication(
            publication_id="der-aktionaer-epaper",
            name="Der Aktionär",
            subscription_id="123",
        ),
        create_mock_publication(
            publication_id="megatrend-folger",
            name="Megatrend Folger",
            subscription_id="456",
        ),
    ]

    with (
        patch_mongodb_operations(
            mock_publications=mock_publications, mock_recipients=[]
        ),
        patch_discovery_service(),
        patch_file_operations(),
    ):
        result = await workflow.run_full_workflow()

        # Assertions
        assert result["success"] is True
        assert result["publications_processed"] == 2
        assert result["publications_succeeded"] == 1
        assert result["publications_failed"] == 0
        assert result["publications_skipped"] == 1
        assert len(result["results"]) == 2

        # Check first publication (skipped)
        pub1 = result["results"][0]
        assert pub1.success is True
        assert pub1.publication_id == "der-aktionaer-epaper"
        assert pub1.already_processed is True
        assert pub1.edition.title == mock_edition_1.title

        # Check second publication (processed)
        pub2 = result["results"][1]
        assert pub2.success is True
        assert pub2.publication_id == "megatrend-folger"
        assert pub2.already_processed is False
        assert pub2.edition.title == mock_edition_2.title
        assert pub2.email_result is True
        assert pub2.upload_result.success is True

        # Verify downloads only happened for second publication
        assert workflow.boersenmedien_client.get_latest_edition.call_count == 2
        assert workflow.boersenmedien_client.download_edition.call_count == 1
        assert workflow.onedrive_service.upload_file.call_count == 1
        assert workflow.email_service.send_pdf_to_recipients.call_count == 1
        assert workflow.edition_tracker.mark_as_processed.call_count == 1


@pytest.mark.asyncio
async def test_workflow_two_publications_one_succeeds_one_fails(
    workflow_with_services, mock_edition_1, mock_edition_2
):
    """Test workflow with 2 publications: 1 succeeds, 1 fails to get edition."""
    workflow = workflow_with_services

    # Define side_effect: first publication succeeds, second returns None (failure)
    def get_edition_side_effect(publication):
        if publication.id == "der-aktionaer-epaper":
            return mock_edition_1
        else:
            return None  # Simulates failure to get edition

    workflow.boersenmedien_client.get_latest_edition.side_effect = (
        get_edition_side_effect
    )
    workflow.boersenmedien_client.get_publication_date.side_effect = lambda ed: ed

    mock_publications = [
        create_mock_publication(
            publication_id="der-aktionaer-epaper",
            name="Der Aktionär",
            subscription_id="123",
        ),
        create_mock_publication(
            publication_id="megatrend-folger",
            name="Megatrend Folger",
            subscription_id="456",
        ),
    ]

    with (
        patch_mongodb_operations(
            mock_publications=mock_publications, mock_recipients=[]
        ),
        patch_discovery_service(),
        patch_file_operations(),
    ):
        result = await workflow.run_full_workflow()

        # Workflow completes but with failures
        assert result["success"] is False  # False because one publication failed
        assert result["publications_processed"] == 2
        assert result["publications_succeeded"] == 1
        assert result["publications_failed"] == 1
        assert result["publications_skipped"] == 0
        assert len(result["results"]) == 2

        # Check first publication (success)
        pub1 = result["results"][0]
        assert pub1.success is True
        assert pub1.publication_id == "der-aktionaer-epaper"
        assert pub1.edition.title == mock_edition_1.title
        assert pub1.email_result is True
        assert pub1.upload_result.success is True

        # Check second publication (failed)
        pub2 = result["results"][1]
        assert pub2.success is False
        assert pub2.publication_id == "megatrend-folger"
        assert pub2.error == "Failed to get latest edition"

        # Only first publication fully processed
        assert workflow.boersenmedien_client.get_latest_edition.call_count == 2
        assert workflow.boersenmedien_client.download_edition.call_count == 1
        assert workflow.onedrive_service.upload_file.call_count == 1
        assert workflow.email_service.send_pdf_to_recipients.call_count == 1
        assert workflow.edition_tracker.mark_as_processed.call_count == 1


@pytest.mark.asyncio
async def test_workflow_no_active_publications(workflow_with_services):
    """Test workflow when there are no active publications."""
    workflow = workflow_with_services

    with (
        patch_mongodb_operations(mock_publications=[], mock_recipients=[]),
        patch_discovery_service(),
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

        # Verify no processing occurred
        workflow.boersenmedien_client.get_latest_edition.assert_not_called()
        workflow.boersenmedien_client.download_edition.assert_not_called()
        workflow.onedrive_service.upload_file.assert_not_called()
        workflow.email_service.send_pdf_to_recipients.assert_not_called()
