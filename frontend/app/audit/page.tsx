import { EmptyState } from "@/components/ui/EmptyState";

export default function AuditPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-950">Audit</h1>
      <EmptyState
        title="Audit activity"
        description="State-changing requests and actor activity will appear here."
      />
    </div>
  );
}
