"use client";

import Link from "next/link";
import { RoleAwareNav } from "./RoleAwareNav";
import { useAuth } from "@/lib/auth";

export function AppShell({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const { user, signOut, loading } = useAuth();

  if (loading) return <>{children}</>;
  if (!user) return <>{children}</>;

  return (
    <div className="min-h-screen bg-canvas text-ink">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-slate-200 bg-white lg:flex lg:flex-col">
        <Link
          href="/dashboard"
          className="flex h-16 items-center border-b border-slate-200 px-6"
        >
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand text-sm font-bold text-white">
            CD
          </div>
          <div className="ml-3">
            <p className="font-semibold">CloudDesk</p>
            <p className="text-xs text-slate-500">Support Console</p>
          </div>
        </Link>
        <RoleAwareNav />
        <div className="border-t border-slate-200 p-4">
          <div className="rounded-lg bg-slate-50 px-3 py-3">
            <p className="text-xs font-medium text-slate-500">Signed in as</p>
            <p className="mt-1 truncate text-sm font-semibold">
              {user.full_name}
            </p>
            <p className="mt-0.5 text-xs capitalize text-slate-500">
              {user.role}
            </p>
          </div>
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-slate-200 bg-white px-4 lg:px-8">
          <div className="lg:hidden">
            <Link href="/dashboard" className="font-semibold">
              CloudDesk
            </Link>
          </div>
          <p className="hidden text-sm text-slate-500 lg:block">
            Support operations
          </p>
          <button
            type="button"
            onClick={signOut}
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium hover:bg-slate-50"
            aria-label="Sign out"
          >
            Sign out
          </button>
        </header>
        <main className="mx-auto max-w-[1440px] p-4 lg:p-8">{children}</main>
      </div>
    </div>
  );
}
