import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TicketWorkflowPanel } from "@/components/tickets/TicketWorkflowPanel";

const workflow = {
  workflow_id: "workflow-1",
  status: "running",
  ticket_id: "ticket-1",
  thread_id: "workflow-1",
  state: {
    completed_nodes: ["understand_ticket", "troubleshooting"],
    current_node: "resolution_planning",
    evidence: [
      {
        id: "evidence-1",
        title: "MFA Recovery",
        source: "kb://mfa-recovery#steps",
        snippet: "Verify MFA enrollment before reset.",
      },
    ],
    diagnosis: {
      probable_causes: ["Expired MFA enrollment"],
      steps: ["Verify enrollment", "Reset session"],
    },
    resolution: {
      customer_reply: "Please verify MFA enrollment.",
      actions: [
        { tool: "create_refund_request", approval_required: true },
        { tool: "update_ticket", approval_required: false },
      ],
    },
  },
};

describe("TicketWorkflowPanel", () => {
  it("renders evidence, diagnosis, proposed actions, and reply", () => {
    render(<TicketWorkflowPanel workflow={workflow} events={[]} canAct />);

    expect(screen.getByText("MFA Recovery")).toBeInTheDocument();
    expect(screen.getByText("kb://mfa-recovery#steps")).toBeInTheDocument();
    expect(screen.getByText("Expired MFA enrollment")).toBeInTheDocument();
    expect(screen.getByText("create_refund_request")).toBeInTheDocument();
    expect(screen.getByText("Approval required")).toBeInTheDocument();
    expect(screen.getByText("update_ticket")).toBeInTheDocument();
    expect(screen.getByLabelText("Editable customer reply")).toHaveValue(
      "Please verify MFA enrollment.",
    );
  });

  it("disables editable reply for viewers", () => {
    render(
      <TicketWorkflowPanel workflow={workflow} events={[]} canAct={false} />,
    );

    expect(screen.getByLabelText("Editable customer reply")).toBeDisabled();
  });

  it("shows empty workflow guidance before a run", () => {
    render(<TicketWorkflowPanel workflow={null} events={[]} canAct />);

    expect(
      screen.getByText("No workflow has been started."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Evidence will appear after the workflow retrieves knowledge.",
      ),
    ).toBeInTheDocument();
  });

  it("renders recent workflow activity safely", () => {
    render(
      <TicketWorkflowPanel
        workflow={workflow}
        events={[
          {
            id: "event-1",
            ticket_id: "ticket-1",
            workflow_id: "workflow-1",
            event_type: "node_completed",
            node_name: "troubleshooting",
            payload: null,
            duration_ms: 12,
            token_usage: null,
            created_at: "2026-11-22T00:00:00Z",
          },
        ]}
        canAct
      />,
    );

    expect(screen.getByText("Recent activity")).toBeInTheDocument();
    expect(screen.getByText("Node Completed")).toBeInTheDocument();
    expect(screen.getByText("Node: troubleshooting")).toBeInTheDocument();
  });
});
