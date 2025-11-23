"""Database layer for MongoDB operations."""

from depotbutler.db.mongodb import get_active_recipients, update_recipient_stats

__all__ = ["get_active_recipients", "update_recipient_stats"]
