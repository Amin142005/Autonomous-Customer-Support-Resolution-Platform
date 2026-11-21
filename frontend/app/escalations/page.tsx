"use client";

import Link from "next/link";
import { useCallback } from "react";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { usePolling } from "@/lib/hooks";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingState } from "@/components/ui/LoadingState";
import { NetworkErrorBanner } from "@/components/ui/NetworkErrorBanner";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusPill } from "@/components/ui/StatusPill";

export default function EscalationsPage() {
  const loader = useCallback(() => api.listEscalations({ limit: 100 }), []);
  const { data, loading, error, reload } = usePolling(loader, 10000);

  if (loading) return <LoadingState label="Loading escalations..." />;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Policy routing"
        title="Escalations"
        description="Cases assigned to named specialist teams."
      />
      {error ? (
        <NetworkErrorBanner message={error} onRetry={() => void reload()} />
      ) : null}

      {data?.items.length ? (
        <div className="grid gap-4">
          {data.items.map((escalation) => (
            <div
              key={escalation.id}
              className="rounded-xl border border-slate-200 bg-white p-5"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="font-semibold text-slate-950">
                    {escalation.team}
                  </p>
                  <p className="mt-1 text-sm text-slate-600">
                    {escalation.reason}
                  </p>
                </div>
                <StatusPill value={escalation.status} tone="danger" />
              </div>
              <div className="mt-4 flex flex-wrap items-center gap-4 text-xs text-slate-500">
                <Link
                  href={`/tickets/${escalation.ticket_id}`}
                  className="font-semibold text-brand hover:underline"
                >
                  View ticket
                </Link>
                <span>Created {formatDate(escalation.created_at)}</span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState
          title="No open escalations"
          description="No policy-routed cases are currently open."
        />
      )}
    </div>
  );
}
