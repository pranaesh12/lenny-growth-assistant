"""
Generic base repository.

Provides common CRUD operations shared by every model-specific
repository. Contains ONLY database access logic — no business rules,
no LLM calls, and no awareness of FastAPI, HTTP requests, or Pydantic
schemas. Each concrete repository (SessionRepository,
MessageRepository, etc.) inherits from this class and adds
model-specific query methods on top.
"""

from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Generic repository providing common CRUD operations for a single
    SQLAlchemy model.

    Subclasses fix `ModelType` to a specific model (e.g. `Session`,
    `Message`) and may add additional, model-specific query methods.
    This class intentionally does not commit transactions implicitly
    beyond what each operation requires — callers (service layer, in
    a later phase) are responsible for wrapping multi-step operations
    in a single unit of work if needed.
    """

    def __init__(self, db: Session, model: type[ModelType]) -> None:
        """
        Args:
            db: An active SQLAlchemy ORM session, typically injected
                via the `get_db()` FastAPI dependency.
            model: The SQLAlchemy model class this repository
                operates on.
        """
        self.db = db
        self.model = model

    def create(self, **fields: Any) -> ModelType:
        """
        Creates and persists a new row.

        Args:
            **fields: Column values to set on the new instance.

        Returns:
            The newly created, persisted model instance (refreshed
            with any database-generated defaults, e.g. `id`,
            `created_at`).
        """
        instance = self.model(**fields)
        self.db.add(instance)
        self.db.commit()
        self.db.refresh(instance)
        return instance

    def get_by_id(self, id_: Any) -> ModelType | None:
        """
        Fetches a single row by primary key.

        Args:
            id_: The primary key value to look up.

        Returns:
            The matching model instance, or None if no row exists
            with that primary key.
        """
        return self.db.get(self.model, id_)

    def get_all(self, skip: int = 0, limit: int = 100) -> list[ModelType]:
        """
        Fetches multiple rows with pagination.

        Args:
            skip: Number of rows to skip (offset).
            limit: Maximum number of rows to return.

        Returns:
            A list of matching model instances, possibly empty.
        """
        statement = select(self.model).offset(skip).limit(limit)
        return list(self.db.execute(statement).scalars().all())

    def update(self, id_: Any, **fields: Any) -> ModelType | None:
        """
        Updates an existing row's fields by primary key.

        Args:
            id_: The primary key of the row to update.
            **fields: Column values to set on the instance.

        Returns:
            The updated model instance, or None if no row exists
            with that primary key.
        """
        instance = self.get_by_id(id_)
        if instance is None:
            return None

        for field_name, value in fields.items():
            setattr(instance, field_name, value)

        self.db.commit()
        self.db.refresh(instance)
        return instance

    def delete(self, id_: Any) -> bool:
        """
        Deletes a row by primary key.

        Args:
            id_: The primary key of the row to delete.

        Returns:
            True if a row was found and deleted, False if no row
            existed with that primary key.
        """
        instance = self.get_by_id(id_)
        if instance is None:
            return False

        self.db.delete(instance)
        self.db.commit()
        return True