import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TicketMessagesColumn } from "@/components/tickets/TicketMessagesColumn";
import { TicketCustomerColumn } from "@/components/tickets/TicketCustomerColumn";
import type { TicketDetail } from "@/lib/types";

const ticket: TicketDetail = {
  id: "ticket-1",
  number: "CD-1002",
  customer_id: "customer-1",
  workspace_id: null,
  subject: "Refund requested",
  body: "Charged for eight seats.",
  channel: "email",
  category: "billing",
  severity: "medium",
  status: "waiting_on_approval",
  summary: null,
  assignee_id: null,
  created_at: "2026-11-21T00:00:00Z",
  updated_at: "2026-11-21T00:00:00Z",
  customer: {
    id: "customer-1",
    name: "Avery Morgan",
    email: "avery@example.test",
    company: "Example Co",
    plan: "business",
  },
  workspace: null,
  messages: [],
};

describe("P13-1 ticket layout components", () => {
  it("disables the reply composer for read-only users", () => {
    render(<TicketMessagesColumn messages={[]} canCompose={false} />);

    expect(screen.getByLabelText("Reply or internal note")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Send reply" })).toBeDisabled();
  });

  it("shows the customer and ticket context column", () => {
    render(<TicketCustomerColumn ticket={ticket} />);

    expect(screen.getByText("Avery Morgan")).toBeInTheDocument();
    expect(screen.getByText("CD-1002")).toBeInTheDocument();
    expect(screen.getByText("Original request")).toBeInTheDocument();
  });
});
