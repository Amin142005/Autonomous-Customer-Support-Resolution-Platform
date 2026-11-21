import { EmptyState } from "@/components/ui/EmptyState";

export default function AgentsPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-950">Agents</h1>
      <EmptyState
        title="Agent workflow map"
        description="Graph nodes and specialist status will be shown here."
      />
    </div>
  );
}
