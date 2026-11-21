import { EmptyState } from "@/components/ui/EmptyState";

export default function TicketDetailPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-950">Ticket detail</h1>
      <EmptyState
        title="Workflow screen"
        description="Ticket messages, customer context, evidence, workflow progress, and actions will appear here."
      />
    </div>
  );
}
