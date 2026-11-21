"use client";

import Link from "next/link";
import { useCallback } from "react";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/hooks";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingState } from "@/components/ui/LoadingState";
import { NetworkErrorBanner } from "@/components/ui/NetworkErrorBanner";
import { PageHeader } from "@/components/ui/PageHeader";

export default function DashboardPage() {
  const loader = useCallback(async () => {
    const [tickets, customers, escalations] = await Promise.all([
      api.listTickets({ limit: 100 }),
      api.listCustomers({ limit: 100 }),
      api.listEscalations({ limit: 100 }),
    ]);
    return {
      tickets: tickets.items,
      customers: customers.items,
      escalations: escalations.items,
    };
  }, []);

  const { data, loading, error, reload } = usePolling(loader, 10000);

  if (loading) return <LoadingState label="Loading support overview..." />;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Operations"
        title="Support dashboard"
        description="Current ticket, customer, and escalation activity."
      />
      {error ? (
        <NetworkErrorBanner message={error} onRetry={() => void reload()} />
      ) : null}

      {data ? (
        <div className="grid gap-4 sm:grid-cols-3">
          <Link
            href="/tickets"
            className="rounded-xl border border-slate-200 bg-white p-5 hover:border-slate-300"
          >
            <p className="text-sm text-slate-500">Tickets</p>
            <p className="mt-2 text-3xl font-semibold text-slate-950">
              {data.tickets.length}
            </p>
          </Link>
          <Link
            href="/customers"
            className="rounded-xl border border-slate-200 bg-white p-5 hover:border-slate-300"
          >
            <p className="text-sm text-slate-500">Customers</p>
            <p className="mt-2 text-3xl font-semibold text-slate-950">
              {data.customers.length}
            </p>
          </Link>
          <Link
            href="/escalations"
            className="rounded-xl border border-slate-200 bg-white p-5 hover:border-slate-300"
          >
            <p className="text-sm text-slate-500">Open escalations</p>
            <p className="mt-2 text-3xl font-semibold text-slate-950">
              {data.escalations.length}
            </p>
          </Link>
        </div>
      ) : (
        <EmptyState
          title="No overview available"
          description="Retry when the CloudDesk API is reachable."
        />
      )}
    </div>
  );
}
