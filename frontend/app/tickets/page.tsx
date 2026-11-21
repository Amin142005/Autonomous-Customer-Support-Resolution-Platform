"use client";

import Link from "next/link";
import { useCallback } from "react";
import { api } from "@/lib/api";
import { formatDate, formatLabel } from "@/lib/format";
import { usePolling } from "@/lib/hooks";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingState } from "@/components/ui/LoadingState";
import { NetworkErrorBanner } from "@/components/ui/NetworkErrorBanner";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusPill } from "@/components/ui/StatusPill";

export default function TicketsPage() {
  const loader = useCallback(() => api.listTickets({ limit: 100 }), []);
  const { data, loading, error, reload } = usePolling(loader, 10000);

  if (loading) return <LoadingState label="Loading tickets..." />;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Support queue"
        title="Tickets"
        description="Read-only view of customer support cases."
      />
      {error ? (
        <NetworkErrorBanner message={error} onRetry={() => void reload()} />
      ) : null}

      {data?.items.length ? (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-5 py-3">Ticket</th>
                  <th className="px-5 py-3">Category</th>
                  <th className="px-5 py-3">Severity</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3">Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.items.map((ticket) => (
                  <tr key={ticket.id} className="hover:bg-slate-50">
                    <td className="px-5 py-4">
                      <Link
                        href={`/tickets/${ticket.id}`}
                        className="font-semibold text-brand hover:underline"
                      >
                        {ticket.number}
                      </Link>
                      <p className="mt-1 max-w-md truncate text-slate-600">
                        {ticket.subject}
                      </p>
                    </td>
                    <td className="px-5 py-4 text-slate-600">
                      {formatLabel(ticket.category)}
                    </td>
                    <td className="px-5 py-4">
                      {ticket.severity ? (
                        <StatusPill value={ticket.severity} />
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="px-5 py-4">
                      <StatusPill value={ticket.status} />
                    </td>
                    <td className="px-5 py-4 text-slate-500">
                      {formatDate(ticket.updated_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <EmptyState
          title="No tickets"
          description="No tickets are available in the CloudDesk API."
        />
      )}
    </div>
  );
}
