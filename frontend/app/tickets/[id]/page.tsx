"use client";

import { useCallback } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDate } from "@/lib/format";
import { usePolling } from "@/lib/hooks";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingState } from "@/components/ui/LoadingState";
import { NetworkErrorBanner } from "@/components/ui/NetworkErrorBanner";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusPill } from "@/components/ui/StatusPill";
import { TicketMessagesColumn } from "@/components/tickets/TicketMessagesColumn";
import { TicketCustomerColumn } from "@/components/tickets/TicketCustomerColumn";
import { TicketWorkflowPanel } from "@/components/tickets/TicketWorkflowPanel";
import { TicketActionBar } from "@/components/tickets/TicketActionBar";

export default function TicketDetailPage() {
  const params = useParams<{ id: string }>();
  const ticketId = params.id;
  const { canAct } = useAuth();

  const loader = useCallback(async () => {
    const [ticket, workflow, events] = await Promise.all([
      api.getTicket(ticketId),
      api.getWorkflow(ticketId).catch(() => null),
      api.getWorkflowEvents(ticketId).catch(() => ({ items: [] })),
    ]);
    return { ticket, workflow, events: events.items };
  }, [ticketId]);

  const { data, loading, refreshing, pollingEnabled, error, reload } =
    usePolling(loader, 2000, {
      stopWhen: (result) =>
        result.workflow?.status === "completed" ||
        result.workflow?.status === "paused",
    });

  if (loading) return <LoadingState label="Loading ticket workspace..." />;

  return (
    <div className="space-y-5">
      {error ? (
        <NetworkErrorBanner message={error} onRetry={() => void reload()} />
      ) : null}

      {data ? (
        <>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <PageHeader
              eyebrow="Ticket detail"
              title={`${data.ticket.number} — ${data.ticket.subject}`}
              description={`Updated ${formatDate(data.ticket.updated_at)} · ${data.ticket.channel}`}
            />
            <div className="flex gap-2">
              {data.ticket.severity ? (
                <StatusPill value={data.ticket.severity} />
              ) : null}
              <StatusPill value={data.ticket.status} />
            </div>
          </div>

          {refreshing ? (
            <p className="text-xs font-medium text-slate-500" role="status">
              Refreshing workflow...
            </p>
          ) : pollingEnabled ? null : (
            <p className="text-xs font-medium text-slate-500" role="status">
              Workflow updates complete
            </p>
          )}

          <div className="grid items-start gap-4 lg:grid-cols-2 xl:grid-cols-[minmax(0,1.15fr)_minmax(260px,.75fr)_minmax(320px,1.1fr)]">
            <TicketMessagesColumn
              messages={data.ticket.messages}
              canCompose={canAct}
            />
            <div className="hidden xl:block">
              <TicketCustomerColumn ticket={data.ticket} />
            </div>
            <div>
              <TicketWorkflowPanel
                workflow={data.workflow}
                events={data.events}
                canAct={canAct}
              />
              <div className="mt-4">
                <TicketActionBar
                  ticketId={ticketId}
                  canAct={canAct}
                  approvalId={
                    typeof data.workflow?.state.approval_id === "string"
                      ? data.workflow.state.approval_id
                      : undefined
                  }
                  approvalStatus={
                    typeof data.workflow?.state.approval_status === "string"
                      ? data.workflow.state.approval_status
                      : undefined
                  }
                  onUpdated={() => void reload()}
                />
              </div>
            </div>
          </div>

          <div className="xl:hidden">
            <TicketCustomerColumn ticket={data.ticket} />
          </div>
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
