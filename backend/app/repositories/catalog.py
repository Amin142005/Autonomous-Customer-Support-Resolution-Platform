from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import Incident, Product, SupportArticle
from backend.app.repositories.base import BaseRepository
from backend.app.schemas.common import Category


class ProductRepository(BaseRepository[Product]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Product)


class SupportArticleRepository(BaseRepository[SupportArticle]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, SupportArticle)

    async def get_by_slug(self, slug: str) -> SupportArticle | None:
        statement = select(SupportArticle).where(SupportArticle.slug == slug)
        return await self.session.scalar(statement)

    async def list_by_category(
        self, category: Category, *, limit: int = 100, offset: int = 0
    ) -> list[SupportArticle]:
        if limit < 1:
            raise ValueError("limit must be greater than zero")
        if offset < 0:
            raise ValueError("offset cannot be negative")
        statement = (
            select(SupportArticle)
            .where(SupportArticle.category == category)
            .order_by(SupportArticle.title.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.scalars(statement)
        return list(result.all())


class IncidentRepository(BaseRepository[Incident]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Incident)

    async def list_active(self) -> list[Incident]:
        statement = (
            select(Incident)
            .where(Incident.status.not_in(("resolved", "closed")))
            .order_by(Incident.started_at.desc())
        )
        result = await self.session.scalars(statement)
        return list(result.all())
