import { EmptyState } from "@/components/ui/EmptyState";

export default function KnowledgePage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-950">Knowledge</h1>
      <EmptyState
        title="No knowledge view yet"
        description="Approved support articles will be listed and searchable here."
      />
    </div>
  );
}
