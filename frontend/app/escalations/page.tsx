import { EmptyState } from "@/components/ui/EmptyState";

export default function EscalationsPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-950">Escalations</h1>
      <EmptyState
        title="No escalation view yet"
        description="Named-team escalations will appear here in the workflow console."
      />
    </div>
  );
}
