import { EmptyState } from "@/components/ui/EmptyState";

export default function TicketsPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-950">Tickets</h1>
      <EmptyState
        title="No ticket view yet"
        description="The ticket list will be connected to the typed API client in a later task."
      />
    </div>
  );
}
