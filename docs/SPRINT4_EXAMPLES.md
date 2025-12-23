# Sprint 4: Test Refactoring Examples

**Date**: December 23, 2025
**Status**: Infrastructure Complete ✅ | Examples Documented ✅ | Test Refactoring Pending 🚧

## Overview

Sprint 4 reduces test boilerplate by introducing shared fixtures and helper utilities. This document shows before/after examples and provides a systematic refactoring guide.

## Infrastructure Created

### 1. Shared Fixtures (`tests/conftest.py`)

All workflow tests now have access to 9 pre-configured fixtures:

| Fixture | Purpose | Lines Saved |
| ------- | ------- | ----------- |
| `workflow_with_services` | Pre-wired DepotButlerWorkflow with all services | ~25 per test |
| `workflow_with_services_dry_run` | Same as above but dry_run=True | ~25 per test |
| `mock_boersenmedien_client` | Pre-configured HttpxBoersenmedienClient mock | ~8 per test |
| `mock_onedrive_service` | Pre-configured OneDriveService mock | ~8 per test |
| `mock_email_service` | Pre-configured EmailService mock | ~5 per test |
| `mock_edition_tracker` | Pre-configured EditionTrackingService mock | ~3 per test |
| `mock_settings` | Pre-configured Settings mock | ~15 per test |
| `mock_edition` | Sample Edition object | ~5 per test |
| `mock_publications` | Sample publication data | ~12 per test |
| `mock_recipients` | Sample recipient data | ~5 per test |

**Total**: Up to ~110 lines saved per test that uses all fixtures

### 2. Helper Utilities (`tests/helpers/workflow_setup.py`)

Context managers and factory functions:

- `patch_mongodb_operations(publications, recipients)` - Patches MongoDB operations
- `patch_discovery_service()` - Patches publication discovery service
- `patch_file_operations()` - Patches file system operations
- `create_mock_publication(**kwargs)` - Creates publication with sensible defaults
- `create_mock_recipient(**kwargs)` - Creates recipient with sensible defaults

## Refactoring Pattern

### Example 1: Basic Workflow Test

**Before** (145 lines):

```python
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

        # Mock BrowserBoersenmedienClient (8 lines)
        mock_client.login = AsyncMock()
        mock_client.discover_subscriptions = AsyncMock()
        mock_client.get_latest_edition = AsyncMock(return_value=mock_edition)
        mock_client.get_publication_date = AsyncMock(return_value=mock_edition)
        mock_client.download_edition = AsyncMock()
        mock_client.close = AsyncMock()

        # Mock OneDriveService (8 lines)
        mock_onedrive.authenticate = AsyncMock(return_value=True)
        mock_onedrive.upload_file = AsyncMock(
            return_value=UploadResult(
                success=True,
                file_url="https://onedrive.com/test.pdf",
                file_id="test-file-123",
            )
        )
        mock_onedrive.close = AsyncMock()

        # Mock EmailService (2 lines)
        mock_email.send_pdf_to_recipients = AsyncMock(return_value=True)
        mock_email.send_success_notification = AsyncMock(return_value=True)

        # Mock MongoDB (12 lines)
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

        # MongoDB/Discovery patching (20 lines)
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
            # Inject mocked external services FIRST (15 lines)
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

            # Mock file operations (7 lines)
            with (
                patch("pathlib.Path.exists", return_value=True),
                patch("pathlib.Path.mkdir"),
                patch("os.path.exists", return_value=True),
                patch("os.remove"),
            ):
                # ACTUAL TEST LOGIC (25 lines)
                result = await workflow.run_full_workflow()

                # Assertions
                assert result["success"] is True
                assert result["publications_processed"] == 1
                assert result["publications_succeeded"] == 1
                assert result["publications_failed"] == 0
                assert result["publications_skipped"] == 0
                assert result["error"] is None
                assert len(result["results"]) == 1

                pub_result = result["results"][0]
                assert pub_result.success is True
                assert pub_result.edition == mock_edition
                assert pub_result.already_processed is False
                assert pub_result.email_result is True
                assert pub_result.upload_result.success is True

                # Verify calls
                mock_client.login.assert_called_once()
                mock_client.get_latest_edition.assert_called_once()
                mock_client.download_edition.assert_called_once()
                mock_onedrive.authenticate.assert_called_once()
                mock_onedrive.upload_file.assert_called_once()
                mock_email.send_pdf_to_recipients.assert_called_once()
                workflow.edition_tracker.mark_as_processed.assert_called_once()
```

**After** (45 lines, 69% reduction):

```python
from tests.helpers.workflow_setup import (
    patch_discovery_service,
    patch_file_operations,
    patch_mongodb_operations,
)


@pytest.mark.asyncio
async def test_full_workflow_success(
    workflow_with_services, mock_edition, mock_publications, mock_recipients
):
    """Test successful execution of the complete workflow."""
    workflow = workflow_with_services

    with (
        patch("depotbutler.workflow.close_mongodb_connection", new_callable=AsyncMock),
        patch("depotbutler.workflow.get_publications", new_callable=AsyncMock, return_value=mock_publications),
        patch_discovery_service(),
        patch_mongodb_operations(mock_publications, mock_recipients),
        *patch_file_operations(),
    ):
        # ACTUAL TEST LOGIC (25 lines) - Same as before!
        result = await workflow.run_full_workflow()

        # Assertions
        assert result["success"] is True
        assert result["publications_processed"] == 1
        assert result["publications_succeeded"] == 1
        assert result["publications_failed"] == 0
        assert result["publications_skipped"] == 0
        assert result["error"] is None
        assert len(result["results"]) == 1

        pub_result = result["results"][0]
        assert pub_result.success is True
        assert pub_result.edition == mock_edition
        assert pub_result.already_processed is False
        assert pub_result.email_result is True
        assert pub_result.upload_result.success is True

        # Verify calls - Access services via workflow
        workflow.boersenmedien_client.login.assert_called_once()
        workflow.boersenmedien_client.get_latest_edition.assert_called_once()
        workflow.boersenmedien_client.download_edition.assert_called_once()
        workflow.onedrive_service.authenticate.assert_called_once()
        workflow.onedrive_service.upload_file.assert_called_once()
        workflow.email_service.send_pdf_to_recipients.assert_called_once()
        workflow.edition_tracker.mark_as_processed.assert_called_once()
```

**Key Changes**:

1. Removed `mock_edition` and `mock_settings` fixture definitions (now in conftest.py)
2. Replaced all mock setup with `workflow_with_services` fixture
3. Replaced manual patching with helper functions
4. Changed assertion access: `mock_client.login` → `workflow.boersenmedien_client.login`

**Result**: 100 lines of boilerplate eliminated, test logic unchanged

### Example 2: Dry-Run Test

**Before** (Similar pattern, ~140 lines):

```python
@pytest.mark.asyncio
async def test_dry_run_mode(mock_edition, mock_settings):
    """Test workflow in dry-run mode."""
    with patch("depotbutler.workflow.Settings", return_value=mock_settings):
        workflow = DepotButlerWorkflow(dry_run=True)  # Only difference!

        # ... 100+ lines of identical setup ...

        # Test logic
        result = await workflow.run_full_workflow()
        assert result["success"]
        # Verify no emails/uploads in dry-run mode
```

**After** (~45 lines):

```python
@pytest.mark.asyncio
async def test_dry_run_mode(
    workflow_with_services_dry_run, mock_edition, mock_publications, mock_recipients
):
    """Test workflow in dry-run mode."""
    workflow = workflow_with_services_dry_run  # Pre-configured with dry_run=True!

    with (
        patch("depotbutler.workflow.close_mongodb_connection", new_callable=AsyncMock),
        patch("depotbutler.workflow.get_publications", new_callable=AsyncMock, return_value=mock_publications),
        patch_discovery_service(),
        patch_mongodb_operations(mock_publications, mock_recipients),
        *patch_file_operations(),
    ):
        # Test logic - unchanged
        result = await workflow.run_full_workflow()
        assert result["success"]
        # Verify no emails/uploads in dry-run mode
```

**Key Change**: Use `workflow_with_services_dry_run` fixture instead of `workflow_with_services`

### Example 3: Custom Configuration

**Need to customize a service mock?** Just override it:

```python
@pytest.mark.asyncio
async def test_download_failure(workflow_with_services, mock_publications, mock_recipients):
    """Test handling of download failures."""
    workflow = workflow_with_services

    # Override the default mock behavior
    workflow.boersenmedien_client.download_edition = AsyncMock(
        side_effect=Exception("Download failed")
    )

    with patch_mongodb_operations(mock_publications, mock_recipients):
        result = await workflow.run_full_workflow()

        assert result["success"] is False
        assert "Download failed" in result["error"]
```

**Pattern**: Get pre-wired workflow, then customize specific behaviors as needed.

## Systematic Refactoring Steps

For each test file:

1. **Add Imports** at top:

   ```python
   from tests.helpers.workflow_setup import (
       patch_discovery_service,
       patch_file_operations,
       patch_mongodb_operations,
   )
   ```

2. **Remove Duplicate Fixtures** - Delete local `mock_edition`, `mock_settings` if they exist

3. **Update Test Signatures** - Add fixture parameters:

   ```python
   # Before:
   async def test_something(mock_edition, mock_settings):

   # After:
   async def test_something(
       workflow_with_services, mock_edition, mock_publications, mock_recipients
   ):
   ```

4. **Replace Setup** - Remove lines 5-100 of boilerplate, replace with:

   ```python
   workflow = workflow_with_services
   ```

5. **Replace Patching** - Replace manual patch blocks with helpers:

   ```python
   with (
       patch("depotbutler.workflow.close_mongodb_connection", new_callable=AsyncMock),
       patch("depotbutler.workflow.get_publications", new_callable=AsyncMock, return_value=mock_publications),
       patch_discovery_service(),
       patch_mongodb_operations(mock_publications, mock_recipients),
       *patch_file_operations(),
   ):
   ```

6. **Update Assertions** - Change mock references:

   ```python
   # Before:
   mock_client.login.assert_called_once()

   # After:
   workflow.boersenmedien_client.login.assert_called_once()
   ```

7. **Test** - Run the individual test: `uv run pytest tests/test_file.py::test_name -xvs`

8. **Commit** - After each successful test refactoring

## Files to Refactor

| File | Tests | Current Lines | Expected Lines | Reduction |
| ---- | ----- | ------------- | -------------- | --------- |
| test_workflow_integration.py | 18 | 947 | ~550 | 42% |
| test_workflow_multi_publication.py | 4 | 612 | ~380 | 38% |
| test_workflow_error_paths.py | 11 | 587 | ~370 | 37% |
| **Total** | **33** | **2146** | **~1300** | **~40%** |

## Benefits Summary

✅ **Maintainability**: Service changes update 1 place (conftest.py), not 33+ tests
✅ **Readability**: Tests focus on behavior, not setup
✅ **Consistency**: All tests use same mocking pattern
✅ **Speed**: Less code to write/review for new tests
✅ **Safety**: Type-checked fixtures reduce test bugs

## Next Steps

1. Refactor `test_workflow_integration.py` (18 tests)
2. Refactor `test_workflow_multi_publication.py` (4 tests)
3. Refactor `test_workflow_error_paths.py` (11 tests)
4. Verify full test suite passes (241 tests)
5. Update CODE_QUALITY.md with completion metrics

**Status**: Ready for systematic refactoring ✅
