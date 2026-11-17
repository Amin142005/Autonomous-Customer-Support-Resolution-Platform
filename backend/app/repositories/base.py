from __future__ import annotations

from typing import Any, Generic, Mapping, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    async def get_by_id(self, entity_id: str) -> ModelT | None:
        return await self.session.get(self.model, entity_id)

    async def list(self, *, limit: int = 100, offset: int = 0) -> list[ModelT]:
        if limit < 1:
            raise ValueError("limit must be greater than zero")
        if offset < 0:
            raise ValueError("offset cannot be negative")

        statement = select(self.model).limit(limit).offset(offset)
        result = await self.session.scalars(statement)
        return list(result.all())

    async def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def create(self, **values: Any) -> ModelT:
        entity = self.model(**values)
        return await self.add(entity)

    async def update(self, entity: ModelT, values: Mapping[str, Any]) -> ModelT:
        mapper = self.model.__mapper__
        updatable_columns = {
            attribute.key
            for attribute in mapper.column_attrs
            if not any(column.primary_key for column in attribute.columns)
        }
        invalid_fields = set(values) - updatable_columns
        if invalid_fields:
            names = ", ".join(sorted(invalid_fields))
            raise ValueError(f"Cannot update unmapped or primary-key fields: {names}")

        for field, value in values.items():
            setattr(entity, field, value)
        await self.session.flush()
        return entity

    async def update_by_id(
        self, entity_id: str, values: Mapping[str, Any]
    ) -> ModelT | None:
        entity = await self.get_by_id(entity_id)
        if entity is None:
            return None
        return await self.update(entity, values)

    async def delete(self, entity: ModelT) -> None:
        await self.session.delete(entity)
        await self.session.flush()

    async def delete_by_id(self, entity_id: str) -> bool:
        entity = await self.get_by_id(entity_id)
        if entity is None:
            return False
        await self.delete(entity)
        return True
