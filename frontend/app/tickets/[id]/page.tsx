"use client";

import { useCallback } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { formatDate, formatLabel } from "@/lib/format";
import { usePolling } from "@/lib/hooks";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingState } from "@/components/ui/LoadingState";
import { NetworkErrorBanner } from "@/components/ui/NetworkErrorBanner";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusPill } from "@/components/ui/StatusPill";

export default function TicketDetailPage() {
  const params = useParams<{ id: string }>();
  const ticketId = params.id;
  const loader = useCallback(async () => {
    const [ticket, workflow, events] = await Promise.all([
      api.getTicket(ticketId),
      api.getWorkflow(ticketId).catch(() => null),
      api.getWorkflowEvents(ticketId).catch(() => ({ items: [] })),
    ]);
    return { ticket, workflow, events: events.items };
  }, [ticketId]);
  const { data, loading, error, reload } = usePolling(loader, 2000);

  if (loading) return <LoadingState label="Loading ticket..." />;

  return (
    <div className="space-y-6">
      {error ? (
        <NetworkErrorBanner message={error} onRetry={() => void reload()} />
      ) : null}
      {data ? (
        <>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <PageHeader
              eyebrow="Ticket detail"
              title={`${data.ticket.number} — ${data.ticket.subject}`}
              description={`Updated ${formatDate(data.ticket.updated_at)}`}
            />
            <div className="flex gap-2">
              {data.ticket.severity ? (
                <StatusPill value={data.ticket.severity} />
              ) : null}
              <StatusPill value={data.ticket.status} />
            </div>
          </div>

          <div className="grid gap-4 xl:grid-cols-[2fr_1fr]">
            <section className="rounded-xl border border-slate-200 bg-white">
              <h2 className="border-b border-slate-200 px-5 py-4 font-semibold text-slate-950">
                Messages
              </h2>
              {data.ticket.messages.length ? (
                <div className="divide-y divide-slate-100">
                  {data.ticket.messages.map((message) => (
                    <article key={message.id} className="px-5 py-4">
                      <div className="flex justify-between gap-3 text-xs text-slate-500">
                        <span className="font-semibold capitalize">
                          {message.author_type}
                        </span>
                        <span>{formatDate(message.created_at)}</span>
                      </div>
                      <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">
                        {message.body}
                      </p>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="px-5 py-6 text-sm text-slate-500">No messages.</p>
              )}
            </section>

            <aside className="space-y-4">
              <section className="rounded-xl border border-slate-200 bg-white p-5">
                <h2 className="font-semibold text-slate-950">Customer</h2>
                <p className="mt-3 font-medium text-slate-700">
                  {data.ticket.customer.name}
                </p>
                <p className="mt-1 text-sm text-slate-500">
                  {data.ticket.customer.email}
                </p>
              </section>

              <section className="rounded-xl border border-slate-200 bg-white p-5">
                <h2 className="font-semibold text-slate-950">Classification</h2>
                <dl className="mt-3 space-y-3 text-sm">
                  <div>
                    <dt className="text-slate-500">Category</dt>
                    <dd className="mt-1 font-medium">
                      {formatLabel(data.ticket.category)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">Channel</dt>
                    <dd className="mt-1 font-medium">
                      {formatLabel(data.ticket.channel)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">Workspace</dt>
                    <dd className="mt-1 font-medium">
                      {data.ticket.workspace?.name ?? "—"}
                    </dd>
                  </div>
                </dl>
              </section>

              <section className="rounded-xl border border-slate-200 bg-white p-5">
                <h2 className="font-semibold text-slate-950">Workflow</h2>
                {data.workflow ? (
                  <>
                    <p className="mt-3 text-sm text-slate-600">
                      {formatLabel(data.workflow.status)}
                    </p>
                    <p className="mt-1 break-all text-xs text-slate-400">
                      {data.workflow.workflow_id}
                    </p>
                  </>
                ) : (
                  <p className="mt-3 text-sm text-slate-500">
                    No workflow has been started.
                  </p>
                )}
              </section>
            </aside>
          </div>

          <section className="rounded-xl border border-slate-200 bg-white">
            <h2 className="border-b border-slate-200 px-5 py-4 font-semibold text-slate-950">
              Workflow events
            </h2>
            {data.events.length ? (
              <div className="divide-y divide-slate-100">
                {data.events.map((event) => (
                  <article key={event.id} className="px-5 py-3 text-sm">
                    <div className="flex flex-wrap justify-between gap-2">
                      <span className="font-medium text-slate-700">
                        {formatLabel(event.event_type)}
                      </span>
                      <span className="text-xs text-slate-500">
                        {formatDate(event.created_at)}
                      </span>
                    </div>
                    {event.node_name ? (
                      <p className="mt-1 text-xs text-slate-500">
                        Node: {event.node_name}
                      </p>
                    ) : null}
                  </article>
                ))}
              </div>
            ) : (
              <p className="px-5 py-6 text-sm text-slate-500">
                No workflow events.
              </p>
            )}
          </section>
        </>
      ) : (
        <EmptyState
          title="Ticket unavailable"
          description="The ticket could not be loaded."
        />
      )}
    </div>
  );
}
