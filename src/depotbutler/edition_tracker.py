"""
Edition tracking service to prevent duplicate processing.
Tracks processed editions using a persistent file that works in Azure Container Apps.
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

from depotbutler.models import Edition
from depotbutler.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ProcessedEdition:
    """Represents a processed edition entry."""

    title: str
    publication_date: str
    download_url: str
    processed_at: str
    file_path: str = ""


class EditionTracker:
    """
    Tracks processed editions to prevent duplicate downloads and emails.

    Uses a JSON file for persistence that can be mounted in Azure Container Apps.
    Automatically cleans up old entries to prevent the file from growing indefinitely.
    """

    def __init__(
        self,
        tracking_file_path: str = "/mnt/data/processed_editions.json",
        retention_days: int = 90,
    ):
        """
        Initialize the edition tracker.

        Args:
            tracking_file_path: Path to the tracking file.
                               Default uses /mnt/data for Azure File Share mounting.
            retention_days: How many days to keep tracking records.
        """
        self.tracking_file = Path(tracking_file_path)
        self.retention_days = retention_days
        self.tracking_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing tracking data
        self.processed_editions: Dict[str, ProcessedEdition] = (
            self._load_tracking_data()
        )

        # Clean up old entries
        self._cleanup_old_entries()

    def _load_tracking_data(self) -> Dict[str, ProcessedEdition]:
        """Load tracking data from file."""
        try:
            if self.tracking_file.exists():
                with open(self.tracking_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return {
                        key: ProcessedEdition(**value) for key, value in data.items()
                    }
            else:
                logger.info("No existing tracking file found at %s", self.tracking_file)
                return {}
        except Exception as e:
            logger.error("Error loading tracking data: %s", e)
            return {}

    def _save_tracking_data(self) -> None:
        """Save tracking data to file."""
        try:
            data = {
                key: asdict(value) for key, value in self.processed_editions.items()
            }

            # Write to temporary file first, then move (atomic operation)
            temp_file = self.tracking_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            temp_file.replace(self.tracking_file)
            logger.debug("Saved tracking data to %s", self.tracking_file)
        except Exception as e:
            logger.error("Error saving tracking data: %s", e)

    def _cleanup_old_entries(self, days_to_keep: Optional[int] = None) -> None:
        """Remove entries older than specified days."""
        try:
            days_to_keep = days_to_keep or self.retention_days
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)

            keys_to_remove = []
            for key, entry in self.processed_editions.items():
                try:
                    processed_date = datetime.fromisoformat(
                        entry.processed_at.replace("Z", "+00:00")
                    )
                    if processed_date < cutoff_date:
                        keys_to_remove.append(key)
                except ValueError:
                    # Invalid date format, remove entry
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                del self.processed_editions[key]

            if keys_to_remove:
                logger.info("Cleaned up %s old tracking entries", len(keys_to_remove))
                self._save_tracking_data()

        except Exception as e:
            logger.error("Error during cleanup: %s", e)

    def _generate_edition_key(self, edition: Edition) -> str:
        """Generate a unique key for an edition."""
        # Use publication date + title for uniqueness
        # This handles cases where title might change slightly but it's the same edition
        return f"{edition.publication_date}_{edition.title}"

    def is_already_processed(self, edition: Edition) -> bool:
        """
        Check if an edition has already been processed.

        Args:
            edition: The edition to check

        Returns:
            True if already processed, False otherwise
        """
        key = self._generate_edition_key(edition)
        is_processed = key in self.processed_editions

        if is_processed:
            existing = self.processed_editions[key]
            logger.info(
                "Edition already processed: %s (%s) - originally processed at %s",
                edition.title,
                edition.publication_date,
                existing.processed_at,
            )

        return is_processed

    def mark_as_processed(self, edition: Edition, file_path: str = "") -> None:
        """
        Mark an edition as processed.

        Args:
            edition: The edition that was processed
            file_path: Optional path to the downloaded file
        """
        key = self._generate_edition_key(edition)

        processed_entry = ProcessedEdition(
            title=edition.title,
            publication_date=edition.publication_date,
            download_url=edition.download_url,
            processed_at=datetime.now().isoformat(),
            file_path=file_path,
        )

        self.processed_editions[key] = processed_entry
        self._save_tracking_data()

        logger.info(
            "Marked edition as processed: %s (%s)",
            edition.title,
            edition.publication_date,
        )

    def get_processed_count(self) -> int:
        """Get the number of processed editions."""
        return len(self.processed_editions)

    def get_recent_editions(self, days: int = 30) -> list[ProcessedEdition]:
        """
        Get editions processed in the last N days.

        Args:
            days: Number of days to look back

        Returns:
            List of processed editions from the last N days
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        recent = []

        for entry in self.processed_editions.values():
            try:
                processed_date = datetime.fromisoformat(
                    entry.processed_at.replace("Z", "+00:00")
                )
                if processed_date >= cutoff_date:
                    recent.append(entry)
            except ValueError:
                continue

        # Sort by processed date (newest first)
        recent.sort(key=lambda x: x.processed_at, reverse=True)
        return recent

    def force_reprocess(self, edition: Edition) -> bool:
        """
        Remove an edition from tracking to allow reprocessing.

        Args:
            edition: The edition to allow reprocessing

        Returns:
            True if the edition was removed from tracking, False if it wasn't tracked
        """
        key = self._generate_edition_key(edition)

        if key in self.processed_editions:
            del self.processed_editions[key]
            self._save_tracking_data()
            logger.info(
                "Removed edition from tracking - will be reprocessed: %s", edition.title
            )
            return True
        else:
            logger.info("Edition was not in tracking: %s", edition.title)
            return False
