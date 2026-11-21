import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TicketActionBar } from "@/components/tickets/TicketActionBar";

vi.mock("@/lib/api", () => ({
  api: {
    replyToTicket: vi.fn(),
    requestTicketInfo: vi.fn(),
    escalateTicket: vi.fn(),
    approve: vi.fn(),
    reject: vi.fn(),
  },
}));

describe("TicketActionBar", () => {
  it("disables all action controls for viewers", () => {
    render(<TicketActionBar ticketId="ticket-1" canAct={false} />);

    expect(screen.getByRole("button", { name: "Send reply" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Request info" })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Escalate ticket" }),
    ).toBeDisabled();
  });

  it("shows approve and reject only for a pending approval", () => {
    const { rerender } = render(
      <TicketActionBar
        ticketId="ticket-1"
        canAct
        approvalStatus="approved"
        approvalId="approval-1"
      />,
    );

    expect(
      screen.queryByRole("button", { name: "Approve" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Reject" }),
    ).not.toBeInTheDocument();

    rerender(
      <TicketActionBar
        ticketId="ticket-1"
        canAct
        approvalStatus="pending"
        approvalId="approval-1"
      />,
    );

    expect(screen.getByRole("button", { name: "Approve" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Reject" })).toBeEnabled();
  });

  it("keeps approve and reject disabled for viewers even with pending approval", () => {
    render(
      <TicketActionBar
        ticketId="ticket-1"
        canAct={false}
        approvalStatus="pending"
        approvalId="approval-1"
      />,
    );

    expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Reject" })).toBeDisabled();
  });
});
