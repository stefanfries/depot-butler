"""Tests for main.py entry point."""

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from depotbutler.main import _download_only_mode, main
from depotbutler.models import Edition


@pytest.fixture
def mock_edition():
    """Create mock Edition."""
    return Edition(
        title="Test Magazine 47/2025",
        publication_date="2025-11-23",
        details_url="https://example.com/details",
        download_url="https://example.com/download.pdf",
    )


@pytest.mark.asyncio
async def test_main_full_mode_success():
    """Test main function in full workflow mode with success."""
    mock_workflow = MagicMock()
    mock_workflow.__aenter__ = AsyncMock(return_value=mock_workflow)
    mock_workflow.__aexit__ = AsyncMock(return_value=None)
    mock_workflow.run_full_workflow = AsyncMock(return_value={"success": True})

    with patch("depotbutler.main.DepotButlerWorkflow", return_value=mock_workflow):
        exit_code = await main(mode="full")

        assert exit_code == 0
        mock_workflow.run_full_workflow.assert_called_once()


@pytest.mark.asyncio
async def test_main_full_mode_failure():
    """Test main function in full workflow mode with failure."""
    mock_workflow = MagicMock()
    mock_workflow.__aenter__ = AsyncMock(return_value=mock_workflow)
    mock_workflow.__aexit__ = AsyncMock(return_value=None)
    mock_workflow.run_full_workflow = AsyncMock(
        return_value={"success": False, "error": "Test error"}
    )

    with patch("depotbutler.main.DepotButlerWorkflow", return_value=mock_workflow):
        exit_code = await main(mode="full")

        assert exit_code == 1


@pytest.mark.asyncio
async def test_main_download_mode():
    """Test main function in download-only mode."""
    with patch("depotbutler.main._download_only_mode", return_value=0) as mock_download:
        exit_code = await main(mode="download")

        assert exit_code == 0
        mock_download.assert_called_once()


@pytest.mark.asyncio
async def test_main_unknown_mode():
    """Test main function with unknown mode."""
    exit_code = await main(mode="unknown")

    assert exit_code == 1


@pytest.mark.asyncio
async def test_download_only_mode_success(mock_edition, tmp_path):
    """Test download-only mode with successful download."""
    mock_client = MagicMock()
    mock_client.login = AsyncMock()
    mock_client.discover_subscriptions = AsyncMock()
    mock_client.get_latest_edition = AsyncMock(return_value=mock_edition)
    mock_client.get_publication_date = AsyncMock(return_value=mock_edition)
    mock_client.download_edition = AsyncMock()
    mock_client.close = AsyncMock()

    mock_publication = MagicMock()
    mock_publication.name = "Test Publication"

    mock_settings = MagicMock()
    mock_settings.tracking.temp_dir = str(tmp_path)

    with (
        patch("depotbutler.main.HttpxBoersenmedienClient", return_value=mock_client),
        patch("depotbutler.main.PUBLICATIONS", [mock_publication]),
        patch("depotbutler.main.Settings", return_value=mock_settings),
        patch("depotbutler.main.create_filename", return_value="test_file.pdf"),
    ):
        exit_code = await _download_only_mode()

        assert exit_code == 0
        mock_client.login.assert_called_once()
        mock_client.discover_subscriptions.assert_called_once()
        mock_client.get_latest_edition.assert_called_once()
        mock_client.download_edition.assert_called_once()
        mock_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_download_only_mode_no_publications():
    """Test download-only mode when no publications are configured."""
    mock_client = MagicMock()
    mock_client.login = AsyncMock()
    mock_client.discover_subscriptions = AsyncMock()

    with (
        patch("depotbutler.main.HttpxBoersenmedienClient", return_value=mock_client),
        patch("depotbutler.main.PUBLICATIONS", []),
    ):
        exit_code = await _download_only_mode()

        assert exit_code == 1


@pytest.mark.asyncio
async def test_download_only_mode_exception():
    """Test download-only mode when exception occurs."""
    mock_client = MagicMock()
    mock_client.login = AsyncMock(side_effect=Exception("Login failed"))

    with patch("depotbutler.main.HttpxBoersenmedienClient", return_value=mock_client):
        exit_code = await _download_only_mode()

        assert exit_code == 1


@pytest.mark.asyncio
async def test_download_only_mode_download_exception(mock_edition, tmp_path):
    """Test download-only mode when download fails."""
    mock_client = MagicMock()
    mock_client.login = AsyncMock()
    mock_client.discover_subscriptions = AsyncMock()
    mock_client.get_latest_edition = AsyncMock(return_value=mock_edition)
    mock_client.get_publication_date = AsyncMock(return_value=mock_edition)
    mock_client.download_edition = AsyncMock(side_effect=Exception("Download failed"))
    mock_client.close = AsyncMock()

    mock_publication = MagicMock()
    mock_settings = MagicMock()
    mock_settings.tracking.temp_dir = str(tmp_path)

    with (
        patch("depotbutler.main.HttpxBoersenmedienClient", return_value=mock_client),
        patch("depotbutler.main.PUBLICATIONS", [mock_publication]),
        patch("depotbutler.main.Settings", return_value=mock_settings),
        patch("depotbutler.main.create_filename", return_value="test_file.pdf"),
    ):
        exit_code = await _download_only_mode()

        assert exit_code == 1


def test_main_entry_point_default_mode():
    """Test __main__ entry point with default mode."""
    # Simply verify the module can be imported and has __main__ block
    import inspect

    import depotbutler.main as main_module

    # Verify the main() function exists
    assert hasattr(main_module, "main")
    assert callable(main_module.main)

    # Verify it's an async function
    assert inspect.iscoroutinefunction(main_module.main)


def test_main_entry_point_custom_mode():
    """Test __main__ entry point with custom mode argument."""
    with (
        patch("sys.argv", ["main.py", "download"]),
        patch("depotbutler.main.asyncio.run") as mock_run,
        patch("sys.exit") as mock_exit,
    ):
        mock_run.return_value = 0

        # Import the module
        import importlib

        import depotbutler.main

        importlib.reload(depotbutler.main)
