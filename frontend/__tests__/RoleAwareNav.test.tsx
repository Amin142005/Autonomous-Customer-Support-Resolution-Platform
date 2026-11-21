import { describe, expect, it } from "vitest";
import { isNavVisible } from "@/components/layout/RoleAwareNav";

const settingsItem = {
  label: "Settings",
  href: "/settings",
  description: "Workspace configuration",
};

const auditItem = {
  label: "Audit",
  href: "/audit",
  description: "System activity",
};

describe("RoleAwareNav", () => {
  it("keeps Settings and Audit hidden from viewers", () => {
    expect(isNavVisible(settingsItem, "viewer")).toBe(false);
    expect(isNavVisible(auditItem, "viewer")).toBe(false);
  });

  it("shows Settings only to admins", () => {
    expect(isNavVisible(settingsItem, "agent")).toBe(false);
    expect(isNavVisible(settingsItem, "admin")).toBe(true);
  });

  it("shows Audit to agents and admins", () => {
    expect(isNavVisible(auditItem, "agent")).toBe(true);
    expect(isNavVisible(auditItem, "admin")).toBe(true);
  });
});
