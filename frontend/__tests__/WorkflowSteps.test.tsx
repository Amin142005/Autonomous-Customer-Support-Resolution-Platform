import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  deriveSteps,
  WORKFLOW_STEPS,
  WorkflowSteps,
} from "@/components/tickets/WorkflowSteps";

describe("WorkflowSteps", () => {
  it("defines all 12 workflow stages", () => {
    expect(WORKFLOW_STEPS).toHaveLength(12);
  });

  it("marks completed and current nodes without losing pending nodes", () => {
    const steps = deriveSteps(
      ["understand_ticket", "classify_severity"],
      "customer_context",
    );

    expect(steps[0].status).toBe("completed");
    expect(steps[1].status).toBe("completed");
    expect(steps[2].status).toBe("current");
    expect(steps[11].status).toBe("pending");
  });

  it("renders an ordered workflow list", () => {
    render(
      <WorkflowSteps
        completedNodes={["understand_ticket"]}
        currentNode="classify_severity"
      />,
    );

    expect(
      screen.getByRole("list", { name: "Workflow steps" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Understand Ticket")).toBeInTheDocument();
    expect(screen.getByText("Memory Update")).toBeInTheDocument();
  });
});
