"""Repository pattern for MongoDB collections."""

from depotbutler.db.repositories.base import BaseRepository
from depotbutler.db.repositories.config import ConfigRepository
from depotbutler.db.repositories.edition import EditionRepository
from depotbutler.db.repositories.publication import PublicationRepository
from depotbutler.db.repositories.recipient import RecipientRepository

__all__ = [
    "BaseRepository",
    "ConfigRepository",
    "EditionRepository",
    "PublicationRepository",
    "RecipientRepository",
]
