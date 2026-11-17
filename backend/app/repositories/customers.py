from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.models.entities import (
    Customer,
    CustomerMemory,
    Subscription,
    Workspace,
)
from backend.app.repositories.base import BaseRepository


class CustomerRepository(BaseRepository[Customer]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Customer)

    async def get_by_email(self, email: str) -> Customer | None:
        statement = select(Customer).where(Customer.email == email)
        return await self.session.scalar(statement)

    async def get_with_context(self, customer_id: str) -> Customer | None:
        statement = (
            select(Customer)
            .where(Customer.id == customer_id)
            .options(
                selectinload(Customer.subscriptions),
                selectinload(Customer.workspaces),
                selectinload(Customer.tickets),
                selectinload(Customer.memory),
            )
        )
        return await self.session.scalar(statement)


class SubscriptionRepository(BaseRepository[Subscription]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Subscription)

    async def list_for_customer(self, customer_id: str) -> list[Subscription]:
        statement = (
            select(Subscription)
            .where(Subscription.customer_id == customer_id)
            .order_by(Subscription.created_at.desc())
        )
        result = await self.session.scalars(statement)
        return list(result.all())


class WorkspaceRepository(BaseRepository[Workspace]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Workspace)

    async def list_for_customer(self, customer_id: str) -> list[Workspace]:
        statement = (
            select(Workspace)
            .where(Workspace.customer_id == customer_id)
            .order_by(Workspace.created_at.desc())
        )
        result = await self.session.scalars(statement)
        return list(result.all())


class CustomerMemoryRepository(BaseRepository[CustomerMemory]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CustomerMemory)

    async def list_for_customer(
        self, customer_id: str, *, limit: int = 10
    ) -> list[CustomerMemory]:
        if limit < 1:
            raise ValueError("limit must be greater than zero")
        statement = (
            select(CustomerMemory)
            .where(CustomerMemory.customer_id == customer_id)
            .order_by(CustomerMemory.created_at.desc())
            .limit(limit)
        )
        result = await self.session.scalars(statement)
        return list(result.all())
