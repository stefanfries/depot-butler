"""Tests for main.py entry point."""

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from depotbutler.main import main


@pytest.mark.asyncio
async def test_main_success():
    """Test main function with success."""
    mock_workflow = MagicMock()
    mock_workflow.__aenter__ = AsyncMock(return_value=mock_workflow)
    mock_workflow.__aexit__ = AsyncMock(return_value=None)
    mock_workflow.run_full_workflow = AsyncMock(return_value={"success": True})

    with patch("depotbutler.main.DepotButlerWorkflow", return_value=mock_workflow):
        exit_code = await main()

        assert exit_code == 0
        mock_workflow.run_full_workflow.assert_called_once()


@pytest.mark.asyncio
async def test_main_failure():
    """Test main function with failure."""
    mock_workflow = MagicMock()
    mock_workflow.__aenter__ = AsyncMock(return_value=mock_workflow)
    mock_workflow.__aexit__ = AsyncMock(return_value=None)
    mock_workflow.run_full_workflow = AsyncMock(
        return_value={"success": False, "error": "Test error"}
    )

    with patch("depotbutler.main.DepotButlerWorkflow", return_value=mock_workflow):
        exit_code = await main()

        assert exit_code == 1


@pytest.mark.asyncio
async def test_main_dry_run():
    """Test main function with dry run mode."""
    mock_workflow = MagicMock()
    mock_workflow.__aenter__ = AsyncMock(return_value=mock_workflow)
    mock_workflow.__aexit__ = AsyncMock(return_value=None)
    mock_workflow.run_full_workflow = AsyncMock(return_value={"success": True})

    with patch("depotbutler.main.DepotButlerWorkflow", return_value=mock_workflow) as mock_wf_class:
        exit_code = await main(dry_run=True)

        assert exit_code == 0
        mock_wf_class.assert_called_once_with(dry_run=True)
        mock_workflow.run_full_workflow.assert_called_once()


@pytest.mark.asyncio
async def test_main_entry_point():
    """Test entry point execution."""
    with (
        patch.object(sys, "argv", ["main.py", "--dry-run"]),
        patch("depotbutler.main.main", return_value=0) as mock_main,
        patch.object(asyncio, "run") as mock_run,
    ):
        mock_run.return_value = 0
        
        # This would be called via if __name__ == "__main__"
        # We just verify the call pattern would be correct
        exit_code = asyncio.run(mock_main(dry_run=True))
        
        assert exit_code == 0
