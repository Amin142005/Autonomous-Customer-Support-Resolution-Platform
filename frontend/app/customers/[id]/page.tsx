import { EmptyState } from "@/components/ui/EmptyState";

export default function CustomerDetailPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-950">Customer detail</h1>
      <EmptyState
        title="Customer profile"
        description="Subscriptions, workspaces, tickets, and safe memory notes will appear here."
      />
    </div>
  );
}
