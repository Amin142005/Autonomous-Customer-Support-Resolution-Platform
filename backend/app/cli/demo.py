from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.core.database import create_database_engine, create_tables
from backend.app.core.config import get_settings
from backend.app.repositories.tickets import TicketRepository
from backend.app.repositories.workflow import (
    ApprovalRequestRepository,
    WorkflowRunRepository,
)
from backend.app.schemas.common import TicketStatus
from backend.app.services.seed_service import bootstrap_demo_data


DEMO_TICKET_NUMBERS = ("CD-1002", "CD-1005")


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the CloudDesk offline approval and escalation demo."
    )
    parser.add_argument(
        "--ticket",
        choices=DEMO_TICKET_NUMBERS,
        help="Run only one scenario (default: run both scenarios).",
    )
    return parser.parse_args(argv)


def format_demo_result(ticket_number: str, status: str, detail: str) -> str:
    return f"{ticket_number}: {status} — {detail}"


async def _prepare_demo_ticket(session, ticket_number: str) -> None:
    ticket = await TicketRepository(session).get_by_number(ticket_number)
    if ticket is None:
        raise LookupError(f"Demo ticket {ticket_number} was not found")

    # A refund amount is clearer in the demo transcript and is the approval policy input.
    if ticket_number == "CD-1002" and "$25.00" not in ticket.body:
        await TicketRepository(session).update(
            ticket,
            {"body": f"{ticket.body} The requested refund amount is $25.00."},
        )

    await TicketRepository(session).update(ticket, {"status": TicketStatus.NEW})

    run_repository = WorkflowRunRepository(session)
    latest = await run_repository.get_latest_for_ticket(ticket.id)
    if latest is not None:
        latest.status = "completed"
        latest.state = latest.state or {}

    await session.flush()


async def _run_demo(ticket_number: str | None) -> list[str]:
    settings = get_settings()
    engine = create_database_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    lines: list[str] = []
    try:
        await create_tables(engine)
        async with session_factory() as session:
            await bootstrap_demo_data(session, settings.sample_data_dir)
            await session.commit()

            selected = (ticket_number,) if ticket_number else DEMO_TICKET_NUMBERS

            for number in selected:
                async with session_factory() as run_session:
                    await _prepare_demo_ticket(run_session, number)
                    await run_session.commit()

                    ticket = await TicketRepository(run_session).get_by_number(number)
                    if ticket is None:
                        raise LookupError(f"Demo ticket {number} was not found")

                    run_repository = WorkflowRunRepository(run_session)
                    run = await run_repository.create(
                        ticket_id=ticket.id,
                        status="paused" if number == "CD-1002" else "completed",
                        state={"ticket_number": number, "demo": True},
                        thread_id=None,
                    )
                    await run_session.flush()

                    if number == "CD-1002":
                        await TicketRepository(run_session).update(
                            ticket,
                            {"status": TicketStatus.WAITING_ON_APPROVAL},
                        )
                        approval_repository = ApprovalRequestRepository(run_session)
                        approval = await approval_repository.get_pending_for_ticket(ticket.id)
                        if approval is None:
                            approval = await approval_repository.create(
                                ticket_id=ticket.id,
                                workflow_id=run.id,
                                action_name="create_refund_request",
                                action_args={
                                    "customer_id": ticket.customer_id,
                                    "amount": "25.00",
                                    "reason": "Duplicate or excess seat refund for demo",
                                },
                                status="pending",
                            )
                        run.thread_id = run.id
                        await run_session.commit()
                        lines.append(format_demo_result(
                            number,
                            "WAITING ON APPROVAL",
                            f"approval_id={approval.id}, action={approval.action_name}",
                        ))

                    elif number == "CD-1005":
                        from agents.specialists.escalation import EscalationAgent
                        from backend.app.schemas.common import Category, Severity
                        from backend.app.services.escalation_service import EscalationService

                        decision = await EscalationAgent().run(
                            {"subject": ticket.subject, "body": ticket.body},
                            category=Category.SECURITY,
                            severity=Severity.CRITICAL,
                        )
                        escalation = await EscalationService(run_session).route(
                            ticket_id=ticket.id,
                            workflow_id=run.id,
                            decision=decision,
                        )
                        run.thread_id = run.id
                        run.status = "completed"
                        await run_session.commit()
                        lines.append(format_demo_result(
                            number,
                            "ESCALATED",
                            f"team={escalation.team}, reason={escalation.reason}",
                        ))

    finally:
        await engine.dispose()

    return lines


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        lines = asyncio.run(_run_demo(args.ticket))
    except (LookupError, OSError, RuntimeError, ValueError) as exc:
        print(f"CloudDesk demo failed: {exc}", file=sys.stderr)
        return 1

    print("CloudDesk offline approval and escalation demo")
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
