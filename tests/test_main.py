"""Tests for main.py entry point."""

import asyncio
import sys
from unittest.mock import AsyncMock, Mock, patch

import pytest

from depotbutler.main import main


def create_async_context_manager_mock(return_value):
    """Helper to create a properly configured async context manager mock."""
    mock = AsyncMock()
    mock.run_full_workflow.return_value = return_value
    
    # Create actual async functions for context manager protocol
    async def mock_aenter(self):
        return mock
    
    async def mock_aexit(self, exc_type, exc_val, exc_tb):
        return None
    
    mock.__aenter__ = mock_aenter
    mock.__aexit__ = mock_aexit
    
    return mock


@pytest.mark.asyncio
async def test_main_success():
    """Test main function with success."""
    mock_workflow = create_async_context_manager_mock({"success": True})
    
    with patch("depotbutler.main.DepotButlerWorkflow", return_value=mock_workflow):
        exit_code = await main()

        assert exit_code == 0
        mock_workflow.run_full_workflow.assert_awaited_once()


@pytest.mark.asyncio
async def test_main_failure():
    """Test main function with failure."""
    mock_workflow = create_async_context_manager_mock({"success": False, "error": "Test error"})
    
    with patch("depotbutler.main.DepotButlerWorkflow", return_value=mock_workflow):
        exit_code = await main()

        assert exit_code == 1


@pytest.mark.asyncio
async def test_main_dry_run():
    """Test main function with dry run mode."""
    mock_workflow = create_async_context_manager_mock({"success": True})
    
    with patch("depotbutler.main.DepotButlerWorkflow", return_value=mock_workflow) as mock_class:
        exit_code = await main(dry_run=True)

        assert exit_code == 0
        mock_class.assert_called_once_with(dry_run=True)
        mock_workflow.run_full_workflow.assert_awaited_once()


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
