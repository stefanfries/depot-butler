"""Metrics tracking for workflow monitoring."""

import time
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from depotbutler.db.mongodb import MongoDBService


class WorkflowMetrics(BaseModel):
    """Metrics data for a complete workflow run."""

    run_id: str = Field(..., description="Unique correlation ID for this run")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    duration_seconds: float = Field(..., description="Total workflow duration")
    operations: dict[str, float] = Field(
        default_factory=dict,
        description="Duration of individual operations (e.g., download, email, upload)",
    )
    editions_processed: int = Field(
        default=0, description="Number of editions processed"
    )
    errors_count: int = Field(default=0, description="Number of errors encountered")
    publication_id: str | None = Field(None, description="Publication being processed")


class WorkflowError(BaseModel):
    """Error event data."""

    run_id: str = Field(..., description="Correlation ID of the run")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    error_type: str = Field(..., description="Exception class name")
    error_message: str = Field(..., description="Error message")
    publication_id: str | None = Field(None, description="Publication being processed")
    operation: str | None = Field(None, description="Operation that failed")
    context: dict[str, Any] = Field(
        default_factory=dict, description="Additional context"
    )


class MetricsTracker:
    """
    Track metrics and errors for a workflow run.

    Usage:
        tracker = MetricsTracker(run_id="run-20260104-183045")
        tracker.start_timer("download")
        # ... perform download ...
        tracker.stop_timer("download")
        await tracker.save_to_mongodb(mongodb)
    """

    def __init__(self, run_id: str, publication_id: str | None = None):
        self.run_id = run_id
        self.publication_id = publication_id
        self.start_time = time.time()
        self._operation_starts: dict[str, float] = {}
        self.operations: dict[str, float] = {}
        self.editions_processed = 0
        self.errors: list[WorkflowError] = []

    def start_timer(self, operation: str) -> None:
        """Start timing an operation."""
        self._operation_starts[operation] = time.time()

    def stop_timer(self, operation: str) -> None:
        """Stop timing an operation and record duration."""
        if operation not in self._operation_starts:
            return
        duration = time.time() - self._operation_starts[operation]
        self.operations[operation] = duration
        del self._operation_starts[operation]

    def record_error(
        self,
        error: Exception,
        operation: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Record an error event."""
        error_event = WorkflowError(
            run_id=self.run_id,
            error_type=type(error).__name__,
            error_message=str(error),
            publication_id=self.publication_id,
            operation=operation,
            context=context or {},
        )
        self.errors.append(error_event)

    def increment_editions(self, count: int = 1) -> None:
        """Increment the count of processed editions."""
        self.editions_processed += count

    def get_metrics(self) -> WorkflowMetrics:
        """Get the current metrics snapshot."""
        total_duration = time.time() - self.start_time
        return WorkflowMetrics(
            run_id=self.run_id,
            duration_seconds=total_duration,
            operations=self.operations.copy(),
            editions_processed=self.editions_processed,
            errors_count=len(self.errors),
            publication_id=self.publication_id,
        )

    async def save_to_mongodb(self, mongodb: MongoDBService) -> None:
        """
        Save metrics and errors to MongoDB.

        Collections:
            - workflow_metrics: Stores WorkflowMetrics documents
            - workflow_errors: Stores WorkflowError documents
        """
        metrics = self.get_metrics()

        # Save metrics
        await mongodb.db["workflow_metrics"].insert_one(metrics.model_dump())

        # Save errors (if any)
        if self.errors:
            error_docs = [error.model_dump() for error in self.errors]
            await mongodb.db["workflow_errors"].insert_many(error_docs)
