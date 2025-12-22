"""Cookie expiration checking service."""

from depotbutler.db.mongodb import get_mongodb_service
from depotbutler.mailer import EmailService
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


class CookieChecker:
    """Service for checking cookie expiration and sending notifications."""

    def __init__(self, email_service: EmailService):
        """
        Initialize cookie checker.

        Args:
            email_service: Email service for sending notifications
        """
        self.email_service = email_service

    async def check_and_notify_expiration(self) -> None:
        """Check cookie expiration and send email notification if expiring soon."""
        try:
            mongodb = await get_mongodb_service()
            expiration_info = await mongodb.get_cookie_expiration_info()

            if not expiration_info:
                return

            days_remaining = expiration_info.get("days_remaining")
            is_expired = expiration_info.get("is_expired")
            expires_at = expiration_info.get("expires_at")

            # Get warning threshold from MongoDB config (default: 5 days)
            warning_days = await mongodb.get_app_config(
                "cookie_warning_days", default=5
            )

            # Only send WARNING notifications based on estimated expiration
            # Let actual login failures trigger error notifications
            if is_expired:
                logger.warning(
                    "⚠️  Authentication cookie estimated to be expired (since %s)",
                    expires_at,
                )
                logger.warning(
                    "   This is based on estimate. Actual login will be attempted."
                )
                # Send warning notification (not error) for estimated expiration
                await self.email_service.send_warning_notification(
                    warning_msg=f"The authentication cookie is estimated to have expired on {expires_at}.<br><br>"
                    f"This is only an estimate based on the manually entered expiration date. "
                    f"The system will still attempt to login. If the actual authentication fails, "
                    f"you will receive a separate error notification.<br><br>"
                    f"Please update the cookie soon using the following command:<br>"
                    f"<code>uv run python scripts/update_cookie_mongodb.py</code>",
                    title="Cookie Likely Expired",
                )
            elif days_remaining is not None and days_remaining <= warning_days:
                logger.warning(
                    f"⚠️  Authentication cookie expires in {days_remaining} days!"
                )
                await self.email_service.send_warning_notification(
                    warning_msg=f"The authentication cookie will expire in {days_remaining} days (on {expires_at}).<br><br>"
                    f"Please update it soon using the following command:<br>"
                    f"<code>uv run python scripts/update_cookie_mongodb.py</code>",
                    title="Cookie Expiring Soon",
                )

        except Exception as e:
            logger.error(f"Failed to check cookie expiration: {e}")
