"use client";

import Link from "next/link";
import { useCallback } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { formatDate, formatLabel } from "@/lib/format";
import { usePolling } from "@/lib/hooks";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingState } from "@/components/ui/LoadingState";
import { NetworkErrorBanner } from "@/components/ui/NetworkErrorBanner";
import { PageHeader } from "@/components/ui/PageHeader";

export default function CustomerDetailPage() {
  const params = useParams<{ id: string }>();
  const customerId = params.id;
  const loader = useCallback(async () => {
    const [customer, history] = await Promise.all([
      api.getCustomer(customerId),
      api.getCustomerTickets(customerId, { limit: 100 }),
    ]);
    return { customer, history: history.items };
  }, [customerId]);
  const { data, loading, error, reload } = usePolling(loader, 10000);

  if (loading) return <LoadingState label="Loading customer..." />;

  return (
    <div className="space-y-6">
      {error ? (
        <NetworkErrorBanner message={error} onRetry={() => void reload()} />
      ) : null}
      {data ? (
        <>
          <PageHeader
            eyebrow="Customer account"
            title={data.customer.name}
            description={data.customer.email}
          />
          <div className="grid gap-4 lg:grid-cols-3">
            <section className="rounded-xl border border-slate-200 bg-white p-5">
              <h2 className="font-semibold text-slate-950">Subscriptions</h2>
              {data.customer.subscriptions.length ? (
                data.customer.subscriptions.map((subscription) => (
                  <div
                    key={subscription.id}
                    className="mt-3 border-t border-slate-100 pt-3 text-sm"
                  >
                    <p className="font-medium">
                      {formatLabel(subscription.plan)}
                    </p>
                    <p className="mt-1 text-slate-500">
                      {subscription.status} · {subscription.seats} seats
                    </p>
                  </div>
                ))
              ) : (
                <p className="mt-3 text-sm text-slate-500">No subscriptions.</p>
              )}
            </section>

            <section className="rounded-xl border border-slate-200 bg-white p-5">
              <h2 className="font-semibold text-slate-950">Workspaces</h2>
              {data.customer.workspaces.length ? (
                data.customer.workspaces.map((workspace) => (
                  <div
                    key={workspace.id}
                    className="mt-3 border-t border-slate-100 pt-3 text-sm"
                  >
                    <p className="font-medium">{workspace.name}</p>
                    <p className="mt-1 text-slate-500">
                      {formatLabel(workspace.status)}
                    </p>
                  </div>
                ))
              ) : (
                <p className="mt-3 text-sm text-slate-500">No workspaces.</p>
              )}
            </section>

            <section className="rounded-xl border border-slate-200 bg-white p-5">
              <h2 className="font-semibold text-slate-950">Safe memory</h2>
              {data.customer.memory.length ? (
                data.customer.memory.map((memory) => (
                  <div
                    key={memory.id}
                    className="mt-3 border-t border-slate-100 pt-3 text-sm"
                  >
                    <p className="text-xs font-semibold uppercase text-brand">
                      {formatLabel(memory.type)}
                    </p>
                    <p className="mt-1 text-slate-600">{memory.content}</p>
                  </div>
                ))
              ) : (
                <p className="mt-3 text-sm text-slate-500">
                  No safe memory notes.
                </p>
              )}
            </section>
          </div>

          <section className="overflow-hidden rounded-xl border border-slate-200 bg-white">
            <h2 className="border-b border-slate-200 px-5 py-4 font-semibold text-slate-950">
              Ticket history
            </h2>
            {data.history.length ? (
              <div className="divide-y divide-slate-100">
                {data.history.map((ticket) => (
                  <Link
                    key={ticket.id}
                    href={`/tickets/${ticket.id}`}
                    className="block px-5 py-4 hover:bg-slate-50"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="font-semibold text-brand">
                        {ticket.number}
                      </p>
                      <p className="text-xs text-slate-500">
                        {formatDate(ticket.updated_at)}
                      </p>
                    </div>
                    <p className="mt-1 text-sm text-slate-600">
                      {ticket.subject}
                    </p>
                  </Link>
                ))}
              </div>
            ) : (
              <p className="px-5 py-6 text-sm text-slate-500">
                No ticket history.
              </p>
            )}
          </section>
        </>
      ) : (
        <EmptyState
          title="Customer unavailable"
          description="The customer could not be loaded."
        />
      )}
    </div>
  );
}
