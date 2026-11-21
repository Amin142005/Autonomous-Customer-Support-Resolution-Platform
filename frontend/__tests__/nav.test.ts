import { describe, expect, it } from "vitest";
import { navItems } from "@/components/layout/nav";

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
});
