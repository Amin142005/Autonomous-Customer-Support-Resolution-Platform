import Link from "next/link";
import { navItems } from "./nav";

export function AppShell({
  children,
}: Readonly<{ children: React.ReactNode }>) {
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
        <nav
          aria-label="Primary navigation"
          className="flex-1 space-y-1 overflow-y-auto px-3 py-5"
        >
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="block rounded-lg px-3 py-2.5 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-950"
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="border-t border-slate-200 p-4">
          <div className="rounded-lg bg-slate-50 px-3 py-3">
            <p className="text-xs font-medium text-slate-500">Signed in as</p>
            <p className="mt-1 text-sm font-semibold">Demo Agent</p>
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
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium hover:bg-slate-50"
            aria-label="Open user menu"
          >
            Agent
          </button>
        </header>
        <main className="mx-auto max-w-[1440px] p-4 lg:p-8">{children}</main>
      </div>
    </div>
  );
}
