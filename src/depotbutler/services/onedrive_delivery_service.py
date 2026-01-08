"""OneDrive delivery service for recipient-specific uploads and archival."""

from depotbutler.models import Edition, UploadResult
from depotbutler.onedrive import OneDriveService
from depotbutler.services.edition_tracking_service import EditionTrackingService
from depotbutler.utils.helpers import create_filename
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


class OneDriveDeliveryService:
    """
    Handles OneDrive delivery operations for publications.

    Manages recipient-specific uploads and archival to default folders.
    """

    def __init__(
        self,
        onedrive_service: OneDriveService,
        edition_tracker: EditionTrackingService,
        dry_run: bool = False,
    ) -> None:
        """
        Initialize OneDrive delivery service.

        Args:
            onedrive_service: OneDrive service instance
            edition_tracker: Edition tracking service
            dry_run: If True, log actions without side effects
        """
        self.onedrive_service = onedrive_service
        self.edition_tracker = edition_tracker
        self.dry_run = dry_run

    async def upload_for_recipients(
        self,
        edition: Edition,
        local_path: str,
        publication_data: dict,
    ) -> UploadResult:
        """
        Upload file to OneDrive with smart folder handling:
        1. Upload once to publication default folder (for recipients without custom folders)
        2. Upload separately for each recipient with a custom_onedrive_folder

        Args:
            edition: Edition being uploaded
            local_path: Local file path
            publication_data: Publication document from MongoDB

        Returns:
            UploadResult with success status (True if at least one upload succeeded)
        """
        try:
            # Authenticate with OneDrive
            auth_success = await self.onedrive_service.authenticate()
            if not auth_success:
                return UploadResult(
                    success=False, error="OneDrive authentication failed"
                )

            # Get recipients with OneDrive enabled for this publication
            from depotbutler.db.mongodb import get_mongodb_service

            mongodb = await get_mongodb_service()
            publication_id = publication_data.get("publication_id")
            assert publication_id is not None

            recipients = await mongodb.get_recipients_for_publication(
                publication_id=publication_id, delivery_method="upload"
            )

            if not recipients:
                logger.info("   ☁️ No OneDrive recipients for this publication")
                return UploadResult(success=True, file_url="No recipients")

            # Separate recipients: those using default folder vs custom folders
            default_folder_recipients = []
            custom_folder_recipients = []

            for recipient in recipients:
                # Check if recipient has a custom folder for this publication
                has_custom = False
                for pref in recipient.get("publication_preferences", []):
                    if pref.get("publication_id") == publication_id and pref.get(
                        "custom_onedrive_folder"
                    ):
                        has_custom = True
                        custom_folder_recipients.append(recipient)
                        break

                if not has_custom:
                    default_folder_recipients.append(recipient)

            successful_uploads = 0
            failed_uploads = 0
            last_error = None
            default_folder_url = None  # Store URL for admin notification

            # 1. Upload once to default folder (if any recipients use it)
            if default_folder_recipients:
                default_folder = publication_data.get("default_onedrive_folder")
                default_organize = publication_data.get("organize_by_year", True)

                recipient_emails = [r["email"] for r in default_folder_recipients]
                logger.info(
                    "   📤 Uploading to default folder for %d recipient(s): %s",
                    len(default_folder_recipients),
                    ", ".join(recipient_emails),
                )

                if self.dry_run:
                    logger.info(
                        "🧪 DRY-RUN: Would upload to folder='%s', organize_by_year=%s",
                        default_folder,
                        default_organize,
                    )
                    successful_uploads += len(default_folder_recipients)
                else:
                    upload_result = await self.onedrive_service.upload_file(
                        local_file_path=local_path,
                        edition=edition,
                        folder_name=default_folder,
                        organize_by_year=default_organize,
                    )

                    if upload_result.success:
                        successful_uploads += len(default_folder_recipients)
                        default_folder_url = (
                            upload_result.file_url
                        )  # Save for notification
                        logger.info("   ✓ Default folder upload successful")
                    else:
                        failed_uploads += len(default_folder_recipients)
                        last_error = upload_result.error
                        logger.error(
                            "   ✗ Default folder upload failed: %s", upload_result.error
                        )

            # 2. Upload separately for each recipient with custom folder
            for recipient in custom_folder_recipients:
                recipient_email = recipient["email"]

                resolved_folder = mongodb.get_onedrive_folder_for_recipient(
                    recipient, publication_data
                )
                resolved_organize = mongodb.get_organize_by_year_for_recipient(
                    recipient, publication_data
                )

                logger.info(
                    "   📤 Uploading to %s's custom folder: %s",
                    recipient_email,
                    resolved_folder,
                )

                if self.dry_run:
                    logger.info(
                        "🧪 DRY-RUN: Would upload for %s to folder='%s', organize_by_year=%s",
                        recipient_email,
                        resolved_folder,
                        resolved_organize,
                    )
                    successful_uploads += 1
                    continue

                upload_result = await self.onedrive_service.upload_file(
                    local_file_path=local_path,
                    edition=edition,
                    folder_name=resolved_folder,
                    organize_by_year=resolved_organize,
                )

                if upload_result.success:
                    successful_uploads += 1
                    logger.info(
                        "   ✓ Custom folder upload successful for %s", recipient_email
                    )
                else:
                    failed_uploads += 1
                    last_error = upload_result.error
                    logger.error(
                        "   ✗ Custom folder upload failed for %s: %s",
                        recipient_email,
                        upload_result.error,
                    )

            # Track OneDrive upload timestamp if at least one upload succeeded (skip in dry-run)
            if successful_uploads > 0 and not self.dry_run:
                edition_key = self.edition_tracker._generate_edition_key(edition)
                if mongodb.edition_repo:
                    await mongodb.edition_repo.update_onedrive_uploaded_timestamp(
                        edition_key
                    )
                    logger.info("   ✓ OneDrive upload timestamp recorded")

            # Return success if at least one upload succeeded
            if successful_uploads > 0:
                # If multiple recipients, include count but keep default folder URL for admin link
                if successful_uploads > 1 and default_folder_url:
                    file_url = f"{default_folder_url}|{successful_uploads}"
                elif default_folder_url:
                    file_url = default_folder_url
                else:
                    file_url = f"{successful_uploads} recipient(s)"

                # Calculate OneDrive file path for MongoDB tracking (if default folder was used)
                onedrive_path = None
                if len(default_folder_recipients) > 0:
                    default_folder = publication_data.get("default_onedrive_folder", "")
                    default_organize = publication_data.get("organize_by_year", True)
                    filename = create_filename(edition)
                    year = edition.publication_date.split("-")[0]
                    if default_organize:
                        onedrive_path = f"{default_folder}/{year}/{filename}"
                    else:
                        onedrive_path = f"{default_folder}/{filename}"

                return UploadResult(
                    success=True,
                    file_url=file_url,
                    onedrive_file_path=onedrive_path,
                )
            else:
                return UploadResult(
                    success=False,
                    error=last_error or "All uploads failed",
                )

        except Exception as e:
            logger.error("OneDrive upload error: %s", e)
            return UploadResult(success=False, error=str(e))

    async def update_file_path_in_mongodb(
        self,
        edition: Edition,
        onedrive_file_path: str | None,
    ) -> None:
        """
        Update file_path in MongoDB to track where the file was uploaded on OneDrive.

        This does NOT upload anything - it just records the path after upload_for_recipients() uploads.

        Args:
            edition: Edition to update file_path for
            onedrive_file_path: OneDrive path where file was uploaded (from upload_for_recipients)
        """
        if not onedrive_file_path:
            logger.debug("   No OneDrive file path to record")
            return

        if self.dry_run:
            logger.info(f"🧪 DRY-RUN: Would set file_path={onedrive_file_path}")
            return

        try:
            from depotbutler.db.mongodb import get_mongodb_service

            mongodb = await get_mongodb_service()
            edition_key = self.edition_tracker._generate_edition_key(edition)

            if mongodb.edition_repo:
                await mongodb.edition_repo.update_file_path(
                    edition_key, onedrive_file_path
                )
                logger.info(f"   ✓ OneDrive file_path recorded: {onedrive_file_path}")

        except Exception as e:
            logger.warning(f"   ⚠️  Failed to update file_path (non-fatal): {e}")
