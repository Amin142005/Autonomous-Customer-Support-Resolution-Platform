import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AppShell } from "@/components/layout/AppShell";

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

describe("AppShell", () => {
  it("renders the CloudDesk brand and primary navigation", () => {
    render(
      <AppShell>
        <div>Page content</div>
      </AppShell>,
    );

    expect(screen.getAllByText("CloudDesk").length).toBeGreaterThan(0);
    expect(
      screen.getByRole("navigation", { name: "Primary navigation" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Tickets" })).toBeInTheDocument();
  });

  it("renders the supplied page content", () => {
    render(
      <AppShell>
        <div>Dashboard content</div>
      </AppShell>,
    );
    expect(screen.getByText("Dashboard content")).toBeInTheDocument();
  });
});
