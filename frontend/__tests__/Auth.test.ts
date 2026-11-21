import { describe, expect, it } from "vitest";
import { roleAtLeast } from "@/lib/auth";

describe("roleAtLeast", () => {
  it("implements viewer < agent < admin", () => {
    expect(roleAtLeast("viewer", "viewer")).toBe(true);
    expect(roleAtLeast("viewer", "agent")).toBe(false);
    expect(roleAtLeast("agent", "agent")).toBe(true);
    expect(roleAtLeast("agent", "admin")).toBe(false);
    expect(roleAtLeast("admin", "viewer")).toBe(true);
    expect(roleAtLeast("admin", "agent")).toBe(true);
  });
});
