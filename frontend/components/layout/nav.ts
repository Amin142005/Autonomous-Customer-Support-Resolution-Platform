export interface NavItem {
  label: string;
  href: string;
  description: string;
}

export const navItems: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", description: "Support overview" },
  { label: "Tickets", href: "/tickets", description: "Customer support cases" },
  { label: "Customers", href: "/customers", description: "Customer accounts" },
  {
    label: "Knowledge",
    href: "/knowledge",
    description: "Approved support articles",
  },
  {
    label: "Escalations",
    href: "/escalations",
    description: "Policy-routed cases",
  },
  { label: "Agents", href: "/agents", description: "Workflow agent status" },
  { label: "Audit", href: "/audit", description: "System activity" },
  {
    label: "Settings",
    href: "/settings",
    description: "Workspace configuration",
  },
  {
    label: "API Health",
    href: "/api/health",
    description: "Service readiness",
  },
];
