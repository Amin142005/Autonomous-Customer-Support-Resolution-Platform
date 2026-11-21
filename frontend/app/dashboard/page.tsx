import { EmptyState } from "@/components/ui/EmptyState";

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm font-medium text-brand">Operations</p>
        <h1 className="text-2xl font-semibold text-slate-950">
          Support dashboard
        </h1>
      </div>
      <EmptyState
        title="Dashboard ready"
        description="Ticket and workflow summaries will appear here as the console pages are implemented."
      />
    </div>
  );
}
