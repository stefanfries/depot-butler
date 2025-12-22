"""Config repository for MongoDB operations."""

from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from depotbutler.db.repositories.base import BaseRepository
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


class ConfigRepository(BaseRepository):
    """Repository for config-related database operations."""

    @property
    def collection(self) -> Any:
        """Return the config collection."""
        return self.db.config

    async def get_auth_cookie(self) -> str | None:
        """
        Get the authentication cookie from MongoDB config collection.

        Returns:
            Cookie value string if found, None otherwise
        """
        try:
            start_time = perf_counter()

            config_doc = await self.collection.find_one({"_id": "auth_cookie"})

            elapsed_ms = (perf_counter() - start_time) * 1000

            if config_doc and config_doc.get("cookie_value"):
                cookie_value = config_doc["cookie_value"]
                logger.info(
                    "Retrieved auth cookie from MongoDB [length=%d, time=%.2fms]",
                    len(cookie_value),
                    elapsed_ms,
                )
                return str(cookie_value)
            else:
                logger.warning(
                    "No auth cookie found in MongoDB [time=%.2fms]", elapsed_ms
                )
                return None

        except Exception as e:
            logger.error("Failed to get auth cookie from MongoDB: %s", e)
            return None

    async def update_auth_cookie(
        self,
        cookie_value: str,
        expires_at: datetime | None = None,
        updated_by: str = "system",
    ) -> bool:
        """
        Update the authentication cookie in MongoDB config collection.

        Args:
            cookie_value: The new cookie value to store
            expires_at: When the cookie expires (optional, from cookie metadata)
            updated_by: Username or identifier of who updated the cookie

        Returns:
            True if update was successful, False otherwise
        """
        try:
            start_time = perf_counter()

            update_data = {
                "cookie_value": cookie_value,
                "updated_at": datetime.now(UTC),
                "updated_by": updated_by,
            }

            if expires_at:
                update_data["expires_at"] = expires_at

            result = await self.collection.update_one(
                {"_id": "auth_cookie"},
                {"$set": update_data},
                upsert=True,
            )

            elapsed_ms = (perf_counter() - start_time) * 1000

            if result.upserted_id or result.modified_count > 0:
                expire_info = f", expires={expires_at}" if expires_at else ""
                logger.info(
                    "Updated auth cookie in MongoDB [updated_by=%s, time=%.2fms%s]",
                    updated_by,
                    elapsed_ms,
                    expire_info,
                )
                return True
            else:
                logger.warning(
                    "Auth cookie update had no effect [time=%.2fms]", elapsed_ms
                )
                return False

        except Exception as e:
            logger.error("Failed to update auth cookie in MongoDB: %s", e)
            return False

    async def get_cookie_expiration_info(self) -> dict | None:
        """
        Get cookie expiration information from MongoDB.

        Returns:
            Dict with expires_at, days_remaining, is_expired, or None if not found
        """
        try:
            config_doc = await self.collection.find_one({"_id": "auth_cookie"})

            if not config_doc:
                return None

            expires_at = config_doc.get("expires_at")
            if not expires_at:
                return {
                    "expires_at": None,
                    "days_remaining": None,
                    "is_expired": None,
                    "warning": "No expiration date stored",
                }

            now = datetime.now(UTC)

            # Ensure expires_at is timezone-aware
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)

            time_remaining = expires_at - now
            days_remaining = time_remaining.days
            is_expired = days_remaining < 0

            return {
                "expires_at": expires_at,
                "days_remaining": days_remaining,
                "is_expired": is_expired,
                "updated_at": config_doc.get("updated_at"),
                "updated_by": config_doc.get("updated_by"),
            }

        except Exception as e:
            logger.error("Failed to get cookie expiration info: %s", e)
            return None

    async def get_app_config(self, key: str, default: Any = None) -> Any:
        """
        Get an application configuration value from MongoDB.

        Args:
            key: Configuration key (e.g., 'log_level', 'cookie_warning_days')
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        try:
            config_doc = await self.collection.find_one({"_id": "app_config"})

            if config_doc and key in config_doc:
                value = config_doc[key]
                if default is not None and value != default:
                    logger.info(
                        "Using MongoDB config for '%s': %s (default: %s)",
                        key,
                        value,
                        default,
                    )
                return value
            else:
                if default is not None:
                    logger.info(
                        "Using default value for '%s': %s (not found in MongoDB)",
                        key,
                        default,
                    )
                return default

        except Exception as e:
            logger.error("Failed to get app config '%s': %s", key, e)
            if default is not None:
                logger.info(
                    "Using default value for '%s': %s (due to error)", key, default
                )
            return default

    async def update_app_config(self, updates: dict) -> bool:
        """
        Update application configuration in MongoDB.

        Args:
            updates: Dict of key-value pairs to update

        Returns:
            True if update was successful, False otherwise
        """
        try:
            result = await self.collection.update_one(
                {"_id": "app_config"},
                {"$set": updates},
                upsert=True,
            )

            if result.upserted_id or result.modified_count > 0:
                logger.info(
                    "Updated app config in MongoDB [keys=%s]",
                    ", ".join(updates.keys()),
                )
                return True
            else:
                logger.warning("App config update had no effect")
                return False

        except Exception as e:
            logger.error("Failed to update app config: %s", e)
            return False
