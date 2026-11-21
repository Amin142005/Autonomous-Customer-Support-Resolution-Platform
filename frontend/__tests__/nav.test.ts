import { describe, expect, it } from "vitest";
import { navItems } from "@/components/layout/nav";
import { roleAtLeast } from "@/lib/auth";

describe("navItems", () => {
  it("declares the CloudDesk console routes once", () => {
    expect(navItems.map((item) => item.href)).toEqual([
      "/dashboard",
      "/tickets",
      "/customers",
      "/knowledge",
      "/escalations",
      "/agents",
      "/audit",
      "/settings",
      "/api/health",
    ]);
  });

  it("uses the CloudDesk role hierarchy", () => {
    expect(roleAtLeast("viewer", "viewer")).toBe(true);
    expect(roleAtLeast("viewer", "agent")).toBe(false);
    expect(roleAtLeast("agent", "agent")).toBe(true);
    expect(roleAtLeast("admin", "agent")).toBe(true);
  });
});
