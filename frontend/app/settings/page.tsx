import { EmptyState } from "@/components/ui/EmptyState";

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-950">Settings</h1>
      <EmptyState
        title="Workspace settings"
        description="Admin configuration controls will be provided in a later task."
      />
    </div>
  );
}
