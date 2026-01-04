"""Tests for observability metrics tracking."""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from depotbutler.observability.metrics import (
    MetricsTracker,
    WorkflowError,
    WorkflowMetrics,
)


class TestWorkflowMetrics:
    """Tests for WorkflowMetrics model."""

    def test_workflow_metrics_initialization(self) -> None:
        """Test WorkflowMetrics can be created with required fields."""
        metrics = WorkflowMetrics(
            run_id="run-test-123",
            duration_seconds=45.67,
        )

        assert metrics.run_id == "run-test-123"
        assert metrics.duration_seconds == 45.67
        assert metrics.operations == {}
        assert metrics.editions_processed == 0
        assert metrics.errors_count == 0
        assert metrics.publication_id is None

    def test_workflow_metrics_with_operations(self) -> None:
        """Test WorkflowMetrics with operation timings."""
        operations = {
            "download": 12.34,
            "email": 5.67,
            "upload": 23.45,
        }

        metrics = WorkflowMetrics(
            run_id="run-test-123",
            duration_seconds=50.0,
            operations=operations,
            editions_processed=3,
            errors_count=1,
            publication_id="megatrend",
        )

        assert metrics.operations == operations
        assert metrics.editions_processed == 3
        assert metrics.errors_count == 1
        assert metrics.publication_id == "megatrend"


class TestWorkflowError:
    """Tests for WorkflowError model."""

    def test_workflow_error_initialization(self) -> None:
        """Test WorkflowError can be created with required fields."""
        error = WorkflowError(
            run_id="run-test-123",
            error_type="ValueError",
            error_message="Invalid value",
        )

        assert error.run_id == "run-test-123"
        assert error.error_type == "ValueError"
        assert error.error_message == "Invalid value"
        assert error.publication_id is None
        assert error.operation is None
        assert error.context == {}

    def test_workflow_error_with_context(self) -> None:
        """Test WorkflowError with additional context."""
        context = {"file": "test.pdf", "attempt": 2}

        error = WorkflowError(
            run_id="run-test-123",
            error_type="DownloadError",
            error_message="Failed to download",
            publication_id="megatrend",
            operation="download",
            context=context,
        )

        assert error.publication_id == "megatrend"
        assert error.operation == "download"
        assert error.context == context


class TestMetricsTracker:
    """Tests for MetricsTracker class."""

    def test_metrics_tracker_initialization(self) -> None:
        """Test MetricsTracker initializes correctly."""
        tracker = MetricsTracker(run_id="run-test-123")

        assert tracker.run_id == "run-test-123"
        assert tracker.publication_id is None
        assert tracker.operations == {}
        assert tracker.editions_processed == 0
        assert len(tracker.errors) == 0

    def test_metrics_tracker_with_publication_id(self) -> None:
        """Test MetricsTracker with publication ID."""
        tracker = MetricsTracker(run_id="run-test-123", publication_id="megatrend")

        assert tracker.publication_id == "megatrend"

    def test_start_and_stop_timer(self) -> None:
        """Test timing an operation."""
        tracker = MetricsTracker(run_id="run-test-123")

        tracker.start_timer("test_operation")
        time.sleep(0.1)  # Sleep 100ms
        tracker.stop_timer("test_operation")

        assert "test_operation" in tracker.operations
        # Should be at least 100ms (0.1s), but allow for timing variance
        assert tracker.operations["test_operation"] >= 0.09

    def test_stop_timer_without_start(self) -> None:
        """Test stopping a timer that was never started."""
        tracker = MetricsTracker(run_id="run-test-123")

        # Should not raise an error
        tracker.stop_timer("nonexistent_operation")

        # Should not record anything
        assert "nonexistent_operation" not in tracker.operations

    def test_multiple_operations(self) -> None:
        """Test tracking multiple operations."""
        tracker = MetricsTracker(run_id="run-test-123")

        tracker.start_timer("op1")
        time.sleep(0.05)
        tracker.stop_timer("op1")

        tracker.start_timer("op2")
        time.sleep(0.05)
        tracker.stop_timer("op2")

        assert "op1" in tracker.operations
        assert "op2" in tracker.operations
        assert len(tracker.operations) == 2

    def test_increment_editions(self) -> None:
        """Test incrementing edition count."""
        tracker = MetricsTracker(run_id="run-test-123")

        assert tracker.editions_processed == 0

        tracker.increment_editions()
        assert tracker.editions_processed == 1

        tracker.increment_editions(5)
        assert tracker.editions_processed == 6

    def test_record_error(self) -> None:
        """Test recording an error."""
        tracker = MetricsTracker(run_id="run-test-123", publication_id="megatrend")

        error = ValueError("Test error")
        tracker.record_error(error, operation="download", context={"file": "test.pdf"})

        assert len(tracker.errors) == 1
        recorded_error = tracker.errors[0]
        assert recorded_error.run_id == "run-test-123"
        assert recorded_error.error_type == "ValueError"
        assert recorded_error.error_message == "Test error"
        assert recorded_error.publication_id == "megatrend"
        assert recorded_error.operation == "download"
        assert recorded_error.context == {"file": "test.pdf"}

    def test_record_multiple_errors(self) -> None:
        """Test recording multiple errors."""
        tracker = MetricsTracker(run_id="run-test-123")

        tracker.record_error(ValueError("Error 1"))
        tracker.record_error(RuntimeError("Error 2"))

        assert len(tracker.errors) == 2
        assert tracker.errors[0].error_type == "ValueError"
        assert tracker.errors[1].error_type == "RuntimeError"

    def test_get_metrics(self) -> None:
        """Test getting metrics snapshot."""
        tracker = MetricsTracker(run_id="run-test-123", publication_id="megatrend")

        # Add some data
        tracker.start_timer("download")
        time.sleep(0.05)
        tracker.stop_timer("download")
        tracker.increment_editions(2)
        tracker.record_error(ValueError("Test error"))

        # Get metrics
        metrics = tracker.get_metrics()

        assert isinstance(metrics, WorkflowMetrics)
        assert metrics.run_id == "run-test-123"
        assert metrics.publication_id == "megatrend"
        assert "download" in metrics.operations
        assert metrics.editions_processed == 2
        assert metrics.errors_count == 1
        assert metrics.duration_seconds > 0

    @pytest.mark.asyncio
    async def test_save_to_mongodb(self) -> None:
        """Test saving metrics to MongoDB."""
        tracker = MetricsTracker(run_id="run-test-123")
        tracker.increment_editions(2)
        tracker.record_error(ValueError("Test error"))

        # Mock MongoDB service
        mock_mongodb = MagicMock()
        mock_db = MagicMock()
        mock_metrics_collection = AsyncMock()
        mock_errors_collection = AsyncMock()

        mock_mongodb.db = mock_db
        mock_db.__getitem__ = MagicMock(
            side_effect=lambda x: {
                "workflow_metrics": mock_metrics_collection,
                "workflow_errors": mock_errors_collection,
            }[x]
        )

        # Save to MongoDB
        await tracker.save_to_mongodb(mock_mongodb)

        # Verify metrics were saved
        mock_metrics_collection.insert_one.assert_called_once()
        saved_metrics = mock_metrics_collection.insert_one.call_args[0][0]
        assert saved_metrics["run_id"] == "run-test-123"
        assert saved_metrics["editions_processed"] == 2

        # Verify errors were saved
        mock_errors_collection.insert_many.assert_called_once()
        saved_errors = mock_errors_collection.insert_many.call_args[0][0]
        assert len(saved_errors) == 1
        assert saved_errors[0]["error_type"] == "ValueError"

    @pytest.mark.asyncio
    async def test_save_to_mongodb_no_errors(self) -> None:
        """Test saving metrics with no errors."""
        tracker = MetricsTracker(run_id="run-test-123")
        tracker.increment_editions(1)

        # Mock MongoDB service
        mock_mongodb = MagicMock()
        mock_db = MagicMock()
        mock_metrics_collection = AsyncMock()
        mock_errors_collection = AsyncMock()

        mock_mongodb.db = mock_db
        mock_db.__getitem__ = MagicMock(
            side_effect=lambda x: {
                "workflow_metrics": mock_metrics_collection,
                "workflow_errors": mock_errors_collection,
            }[x]
        )

        # Save to MongoDB
        await tracker.save_to_mongodb(mock_mongodb)

        # Verify metrics were saved
        mock_metrics_collection.insert_one.assert_called_once()

        # Verify no errors were saved (insert_many should not be called)
        mock_errors_collection.insert_many.assert_not_called()
