import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TicketActionBar } from "@/components/tickets/TicketActionBar";

const apiMocks = vi.hoisted(() => ({
  replyToTicket: vi.fn(),
  requestTicketInfo: vi.fn(),
  escalateTicket: vi.fn(),
  approve: vi.fn(),
  reject: vi.fn(),
}));

vi.mock("@/lib/api", () => ({ api: apiMocks }));

describe("TicketActionBar", () => {
  it("disables all action controls for viewers", () => {
    render(<TicketActionBar ticketId="ticket-1" canAct={false} />);

    expect(screen.getByRole("button", { name: "Send reply" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Request info" })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Escalate ticket" }),
    ).toBeDisabled();
  });

  it("shows approve and reject only for pending approval", () => {
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

  it("keeps approval controls disabled for viewers", () => {
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

  it("submits a reply with agent text", async () => {
    apiMocks.replyToTicket.mockResolvedValue({
      ticket: {},
      message: "recorded",
    });
    render(<TicketActionBar ticketId="ticket-1" canAct />);

    fireEvent.change(screen.getByLabelText("Customer reply"), {
      target: { value: "Please verify MFA enrollment." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send reply" }));

    await waitFor(() => {
      expect(apiMocks.replyToTicket).toHaveBeenCalledWith("ticket-1", {
        body: "Please verify MFA enrollment.",
      });
    });
  });

  it("submits request-info and escalation text", async () => {
    apiMocks.requestTicketInfo.mockResolvedValue({
      ticket: {},
      message: "recorded",
    });
    apiMocks.escalateTicket.mockResolvedValue({
      ticket: {},
      message: "escalated",
    });
    render(<TicketActionBar ticketId="ticket-1" canAct />);

    fireEvent.change(screen.getByLabelText("Customer reply"), {
      target: { value: "Send the affected email address." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Request info" }));

    await waitFor(() => {
      expect(apiMocks.requestTicketInfo).toHaveBeenCalledWith("ticket-1", {
        body: "Send the affected email address.",
      });
    });

    fireEvent.change(screen.getByLabelText("Escalation reason"), {
      target: { value: "Needs specialist review." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Escalate ticket" }));

    await waitFor(() => {
      expect(apiMocks.escalateTicket).toHaveBeenCalledWith("ticket-1", {
        body: "Needs specialist review.",
      });
    });
  });

  it("approves and rejects only the pending approval", async () => {
    apiMocks.approve.mockResolvedValue({});
    apiMocks.reject.mockResolvedValue({});
    render(
      <TicketActionBar
        ticketId="ticket-1"
        canAct
        approvalStatus="pending"
        approvalId="approval-1"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    await waitFor(() => {
      expect(apiMocks.approve).toHaveBeenCalledWith("approval-1", {});
    });

    fireEvent.click(screen.getByRole("button", { name: "Reject" }));
    await waitFor(() => {
      expect(apiMocks.reject).toHaveBeenCalledWith("approval-1", {});
    });
  });
});
