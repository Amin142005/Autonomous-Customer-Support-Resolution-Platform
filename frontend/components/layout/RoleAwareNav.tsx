"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { navItems, type NavItem } from "./nav";

export function isNavVisible(
  item: NavItem,
  role: "viewer" | "agent" | "admin" | undefined,
): boolean {
  if (item.href === "/settings") return role === "admin";
  if (item.href === "/audit") return role === "agent" || role === "admin";
  return Boolean(role);
}

export function RoleAwareNav() {
  const { user } = useAuth();
  const visibleItems = navItems.filter((item) =>
    isNavVisible(item, user?.role),
  );

  return (
    <nav
      aria-label="Primary navigation"
      className="flex-1 space-y-1 overflow-y-auto px-3 py-5"
    >
      {visibleItems.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          title={item.description}
          className="block rounded-lg px-3 py-2.5 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-950"
        >
          {item.label}
        </Link>
      ))}
    </nav>
  );
}
