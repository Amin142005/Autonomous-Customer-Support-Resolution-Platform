import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusPill } from "@/components/ui/StatusPill";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingState } from "@/components/ui/LoadingState";
import { formatDate, formatLabel } from "@/lib/format";

describe("read-page components", () => {
  it("formats status labels and warnings", () => {
    render(<StatusPill value="waiting_on_approval" />);
    expect(screen.getByText("Waiting On Approval")).toBeInTheDocument();
  });

  it("renders empty and loading states", () => {
    const { rerender } = render(
      <EmptyState title="No tickets" description="No cases available" />,
    );
    expect(screen.getByText("No tickets")).toBeInTheDocument();

    rerender(<LoadingState label="Loading tickets..." />);
    expect(screen.getByText("Loading tickets...")).toBeInTheDocument();
  });

  it("formats labels and invalid dates safely", () => {
    expect(formatLabel("waiting_on_approval")).toBe("Waiting On Approval");
    expect(formatDate("not-a-date")).toBe("—");
  });
});
