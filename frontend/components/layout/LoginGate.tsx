"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { useAuth } from "@/lib/auth";

export function LoginGate({ children }: Readonly<{ children: ReactNode }>) {
  const { user, loading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user && pathname !== "/login") {
      router.replace("/login");
    }
  }, [loading, pathname, router, user]);

  if (pathname === "/login") return <>{children}</>;

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-canvas">
        <div className="rounded-xl border border-slate-200 bg-white px-6 py-5 text-sm text-slate-600">
          Restoring your CloudDesk session...
        </div>
      </div>
    );
  }

  if (!user) return null;
  return <>{children}</>;
}
