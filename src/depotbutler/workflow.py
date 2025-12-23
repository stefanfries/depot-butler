"""
Main workflow orchestrator for DepotButler.
Coordinates downloading, uploading to OneDrive, and email notifications.
Includes edition tracking to prevent duplicate processing.
"""

from datetime import datetime
from time import perf_counter
from typing import Any

from depotbutler.db.mongodb import (
    close_mongodb_connection,
    get_mongodb_service,
    get_publications,
)
from depotbutler.exceptions import (
    AuthenticationError,
    ConfigurationError,
    EditionNotFoundError,
    TransientError,
)
from depotbutler.httpx_client import HttpxBoersenmedienClient
from depotbutler.mailer import EmailService
from depotbutler.models import Edition
from depotbutler.onedrive import OneDriveService
from depotbutler.publications import PublicationConfig
from depotbutler.services.cookie_checking_service import CookieCheckingService
from depotbutler.services.edition_tracking_service import EditionTrackingService
from depotbutler.services.notification_service import NotificationService
from depotbutler.services.publication_discovery_service import (
    PublicationDiscoveryService,
)
from depotbutler.services.publication_processing_service import (
    PublicationProcessingService,
    PublicationResult,
)
from depotbutler.settings import Settings
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


class DepotButlerWorkflow:
    """
    Main workflow orchestrator for automated PDF processing.

    Workflow:
    1. Check if edition was already processed (skip if yes)
    2. Login to boersenmedien.com and download latest edition
    3. Send PDF via email to recipients
    4. Upload PDF to OneDrive
    5. Send success notification to admin
    6. Mark edition as processed
    7. Cleanup temporary files
    """

    def __init__(self, tracking_file_path: str | None = None, dry_run: bool = False):
        self.settings = Settings()
        self.boersenmedien_client: HttpxBoersenmedienClient | None = None
        self.onedrive_service: OneDriveService | None = None
        self.email_service: EmailService | None = None
        self.cookie_checker: CookieCheckingService | None = None
        self.notification_service: NotificationService | None = None
        self.publication_processor: PublicationProcessingService | None = None
        self.dry_run = dry_run

        if dry_run:
            logger.warning(
                "🧪 DRY-RUN MODE: No emails will be sent and no files will be uploaded"
            )

        # Note: tracking_file_path parameter is deprecated and ignored
        # Edition tracking now uses MongoDB
        if tracking_file_path:
            logger.warning(
                "tracking_file_path parameter is deprecated - using MongoDB for tracking"
            )

        # Initialize edition tracker - will be upgraded to MongoDB in __aenter__
        # For testing/backwards compatibility, create a sync-compatible dummy tracker
        class SyncDummyTracker:
            """Dummy tracker for testing that supports both sync and async patterns."""

            def is_already_processed(self, edition: Any) -> bool:  # noqa: ARG002, ANN401
                return False

            def mark_as_processed(self, edition: Any, file_path: str = "") -> None:  # noqa: ARG002, ANN401
                pass

            def get_processed_count(self) -> int:
                return 0

            def get_recent_editions(self, days: int) -> list:  # noqa: ARG002
                return []

            def force_reprocess(self, edition: Any) -> bool:  # noqa: ARG002, ANN401
                return False

        self.edition_tracker: Any = (
            SyncDummyTracker()
            if not self.settings.tracking.enabled
            else SyncDummyTracker()
        )
        if not self.settings.tracking.enabled:
            logger.info("Edition tracking is disabled")

    async def __aenter__(self) -> "DepotButlerWorkflow":
        """Async context manager entry."""
        # Use HTTPX-based client (lightweight, no browser needed)
        self.boersenmedien_client = HttpxBoersenmedienClient()
        self.onedrive_service = OneDriveService()
        self.email_service = EmailService()

        # Initialize services
        self.cookie_checker = CookieCheckingService(self.email_service)
        self.notification_service = NotificationService(
            self.email_service, self.dry_run
        )

        # Initialize real edition tracker with MongoDB (if tracking is enabled and not mocked)
        if self.settings.tracking.enabled and not hasattr(
            self.edition_tracker, "_test_mock"
        ):
            mongodb = await get_mongodb_service()

            # Get tracking settings from MongoDB with fallback to .env
            tracking_enabled = await mongodb.get_app_config(
                "tracking_enabled", default=self.settings.tracking.enabled
            )
            retention_days = await mongodb.get_app_config(
                "tracking_retention_days", default=self.settings.tracking.retention_days
            )

            if tracking_enabled:
                self.edition_tracker = EditionTrackingService(
                    mongodb=mongodb,
                    retention_days=retention_days,
                )
                logger.info(
                    "Edition tracking enabled with MongoDB backend [retention_days=%s]",
                    retention_days,
                )
            else:
                logger.info("Edition tracking is disabled via MongoDB config")

        # Initialize publication processor
        self.publication_processor = PublicationProcessingService(
            boersenmedien_client=self.boersenmedien_client,
            onedrive_service=self.onedrive_service,
            email_service=self.email_service,
            edition_tracker=self.edition_tracker,
            settings=self.settings,
            dry_run=self.dry_run,
        )

        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:  # noqa: ANN401
        """Async context manager exit with cleanup."""
        if self.boersenmedien_client:
            await self.boersenmedien_client.close()
        if self.onedrive_service:
            await self.onedrive_service.close()
        # Close MongoDB connection
        await close_mongodb_connection()

    async def run_full_workflow(self) -> dict:
        """
        Execute the complete DepotButler workflow for all active publications.

        Returns:
            Dict with workflow results including list of publication results
        """
        workflow_start = perf_counter()
        workflow_result = self._initialize_workflow_result()

        try:
            logger.info(
                "🚀 Starting DepotButler Multi-Publication Workflow [timestamp=%s]",
                datetime.now().isoformat(),
            )

            # Initialize workflow
            await self._initialize_workflow()

            # Get active publications
            publications = await self._get_active_publications()
            if not publications:
                workflow_result["error"] = "No active publications configured"
                return workflow_result

            # Process all publications
            results = await self._process_all_publications(
                publications, workflow_result
            )
            workflow_result["results"] = results
            workflow_result["publications_processed"] = len(results)

            # Send consolidated notification
            logger.info("📧 Step 5: Sending consolidated notification")
            assert self.notification_service is not None
            await self.notification_service.send_consolidated_notification(results)

            # Determine overall success
            workflow_result["success"] = workflow_result["publications_failed"] == 0

            self._log_workflow_completion(workflow_result, workflow_start)

        except (AuthenticationError, ConfigurationError, TransientError) as e:
            await self._handle_workflow_error(e, workflow_result)
        except Exception as e:
            await self._handle_unexpected_error(e, workflow_result)

        return workflow_result

    def _initialize_workflow_result(self) -> dict[str, Any]:
        """Initialize workflow result dictionary."""
        return {
            "success": False,
            "publications_processed": 0,
            "publications_succeeded": 0,
            "publications_failed": 0,
            "publications_skipped": 0,
            "results": [],
            "error": None,
        }

    async def _initialize_workflow(self) -> None:
        """Initialize workflow by authenticating and syncing."""
        # Check cookie expiration
        assert self.cookie_checker is not None
        await self.cookie_checker.check_and_notify_expiration()

        # Login and discover subscriptions
        logger.info("🔐 Step 1: Authenticating")
        assert self.boersenmedien_client is not None
        await self.boersenmedien_client.login()
        await self.boersenmedien_client.discover_subscriptions()

        # Sync publications if enabled
        if self.settings.discovery.enabled:
            logger.info("🔄 Step 2: Syncing publications from account")
            await self._sync_publications_from_account()

    async def _get_active_publications(self) -> list[dict]:
        """Get all active publications from MongoDB."""
        logger.info("📋 Step 3: Loading active publications")
        publications = await get_publications(active_only=True)

        if not publications:
            logger.warning("⚠️  No active publications found in MongoDB")
            return []

        logger.info(f"Found {len(publications)} active publication(s)")
        return publications

    async def _process_all_publications(
        self, publications: list[dict], workflow_result: dict[str, Any]
    ) -> list[PublicationResult]:
        """Process all publications and update workflow counters."""
        logger.info("📰 Step 4: Processing all publications")
        results: list[PublicationResult] = []

        assert self.publication_processor is not None
        for pub_data in publications:
            try:
                result = await self.publication_processor.process_publication(pub_data)
                results.append(result)
                self._update_workflow_counters(result, workflow_result)

            except Exception as e:
                logger.error(
                    f"❌ Unexpected error processing {pub_data['name']}: {e}",
                    exc_info=True,
                )
                # Create failed result
                failed_result = PublicationResult(
                    publication_id=pub_data["publication_id"],
                    publication_name=pub_data["name"],
                    success=False,
                    error=str(e),
                )
                results.append(failed_result)
                workflow_result["publications_failed"] = (
                    int(workflow_result["publications_failed"]) + 1
                )

        return results

    def _update_workflow_counters(
        self, result: PublicationResult, workflow_result: dict[str, Any]
    ) -> None:
        """Update workflow counters based on publication result."""
        if result.already_processed:
            workflow_result["publications_skipped"] = (
                int(workflow_result["publications_skipped"]) + 1
            )
        elif result.success:
            workflow_result["publications_succeeded"] = (
                int(workflow_result["publications_succeeded"]) + 1
            )
        else:
            workflow_result["publications_failed"] = (
                int(workflow_result["publications_failed"]) + 1
            )

    def _log_workflow_completion(
        self, workflow_result: dict[str, Any], start_time: float
    ) -> None:
        """Log workflow completion summary."""
        elapsed = perf_counter() - start_time
        logger.info(
            f"✅ Workflow completed: {workflow_result['publications_succeeded']} succeeded, "
            f"{workflow_result['publications_skipped']} skipped, "
            f"{workflow_result['publications_failed']} failed "
            f"[total_time=%.2fs]",
            elapsed,
        )

    async def _handle_workflow_error(
        self, error: Exception, workflow_result: dict[str, Any]
    ) -> None:
        """Handle known workflow errors (Authentication, Configuration, Transient)."""
        # Determine error message and notification details based on error type
        if isinstance(error, AuthenticationError):
            error_msg = f"Authentication failed: {str(error)}"
            logger.error(f"❌ {error_msg}")
            workflow_result["error"] = error_msg
            title = "DepotButler Authentication Required"
            message = f"Authentication failed:<br><br>{error_msg}<br><br>Please update your authentication cookie."

        elif isinstance(error, ConfigurationError):
            error_msg = f"Configuration error: {str(error)}"
            logger.error(f"❌ {error_msg}")
            workflow_result["error"] = error_msg
            title = "DepotButler Configuration Error"
            message = f"Configuration error:<br><br>{error_msg}"

        else:  # TransientError
            error_msg = f"Temporary failure: {str(error)}"
            logger.warning(f"⚠️ {error_msg}")
            workflow_result["error"] = error_msg
            title = "DepotButler Temporary Failure"
            message = f"Temporary failure (will retry next run):<br><br>{error_msg}"

        # Send error notification
        assert self.email_service is not None
        await self.email_service.send_error_notification(
            error_msg=message, edition_title=title
        )

    async def _handle_unexpected_error(
        self, error: Exception, workflow_result: dict[str, Any]
    ) -> None:
        """Handle unexpected errors during workflow execution."""
        error_msg = f"Workflow failed: {str(error)}"
        logger.error(f"❌ {error_msg}", exc_info=True)
        workflow_result["error"] = error_msg

        # Send error notification
        assert self.email_service is not None
        await self.email_service.send_error_notification(
            error_msg=f"Multi-publication workflow failed:<br><br>{error_msg}",
            edition_title="DepotButler Workflow Error",
        )

    async def _get_latest_edition_info(self) -> Edition | None:
        """Get information about the latest edition without downloading.

        Note: Assumes client is already logged in and subscriptions are discovered.
        """
        try:
            # Get active publications from MongoDB (fresh from sync)
            publications = await get_publications(active_only=True)
            if not publications:
                logger.error("No active publications found in MongoDB")
                return None

            # Process first active publication (for now - will be expanded later)
            self.current_publication_data = publications[0]
            logger.info(
                "Processing publication: %s", self.current_publication_data["name"]
            )
            logger.info(
                "  Email enabled: %s | OneDrive enabled: %s",
                self.current_publication_data.get("email_enabled", True),
                self.current_publication_data.get("onedrive_enabled", True),
            )

            # Create PublicationConfig for compatibility with existing get_latest_edition
            publication = PublicationConfig(
                id=self.current_publication_data["publication_id"],
                name=self.current_publication_data["name"],
                onedrive_folder=self.current_publication_data.get(
                    "default_onedrive_folder", ""
                ),
                subscription_number=self.current_publication_data.get(
                    "subscription_number"
                ),
                subscription_id=self.current_publication_data.get("subscription_id"),
            )

            # Get latest edition info
            assert self.boersenmedien_client is not None
            edition = await self.boersenmedien_client.get_latest_edition(publication)
            if edition is None:
                return None
            logger.info("Found edition: %s", edition.title)

            # Get publication date
            edition = await self.boersenmedien_client.get_publication_date(edition)
            logger.info("Publication date: %s", edition.publication_date)

            return edition

        except EditionNotFoundError:
            logger.warning("No edition found for publication: %s", publication.name)
            return None
        except TransientError as e:
            logger.warning("Temporary error getting edition: %s", e)
            return None
        except Exception as e:
            logger.error("Failed to get edition info: %s", e)
            return None

    async def _sync_publications_from_account(self) -> None:
        """Synchronize publications from boersenmedien.com account to MongoDB."""
        try:
            logger.info("🔄 Syncing publications from account...")

            # Create discovery service
            assert self.boersenmedien_client is not None
            discovery_service = PublicationDiscoveryService(self.boersenmedien_client)

            # Run synchronization
            sync_results = await discovery_service.sync_publications_from_account()

            # Log results
            if sync_results["new_count"] > 0:
                logger.info(
                    f"✨ Discovered {sync_results['new_count']} new publication(s)"
                )

            if sync_results["errors"]:
                logger.warning(
                    f"⚠️  Sync encountered {len(sync_results['errors'])} error(s)"
                )

            logger.info(
                f"✓ Publication sync complete: "
                f"{sync_results['discovered_count']} total, "
                f"{sync_results['updated_count']} updated"
            )

        except Exception as e:
            logger.error(f"Publication sync failed: {e}", exc_info=True)
            # Don't fail the entire workflow if sync fails
            logger.warning("Continuing workflow despite sync failure")

    async def check_for_new_editions(self) -> dict:
        """
        Check for new editions without processing them.
        Useful for status checks and monitoring.

        Returns:
            Dict with information about available editions
        """
        try:
            edition = await self._get_latest_edition_info()
            if not edition:
                return {"success": False, "error": "Failed to get edition information"}

            is_processed = await self.edition_tracker.is_already_processed(edition)
            recent_editions = await self.edition_tracker.get_recent_editions(
                7
            )  # Last 7 days

            return {
                "success": True,
                "latest_edition": {
                    "title": edition.title,
                    "publication_date": edition.publication_date,
                    "already_processed": is_processed,
                },
                "recent_processed_count": len(recent_editions),
                "total_processed_count": await self.edition_tracker.get_processed_count(),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def force_reprocess_latest(self) -> dict:
        """
        Force reprocessing of the latest edition even if already processed.
        Useful for testing or when reprocessing is needed.
        """
        try:
            edition = await self._get_latest_edition_info()
            if not edition:
                return {"success": False, "error": "Failed to get edition information"}

            # Remove from tracking to allow reprocessing
            was_tracked = await self.edition_tracker.force_reprocess(edition)

            # Run the workflow
            result = await self.run_full_workflow()
            result["was_previously_processed"] = was_tracked

            return result

        except Exception as e:
            return {"success": False, "error": str(e)}


# Main entry point for Azure Container or scheduled execution
async def main() -> int:
    """
    Main entry point for the DepotButler workflow.
    Designed to run in Azure Container Instance as scheduled job.
    """
    async with DepotButlerWorkflow() as workflow:
        result = await workflow.run_full_workflow()

        # Return appropriate exit code for container scheduling
        if result["success"]:
            logger.info("Workflow completed successfully")
            return 0
        else:
            logger.error("Workflow failed: %s", result["error"])
            return 1
