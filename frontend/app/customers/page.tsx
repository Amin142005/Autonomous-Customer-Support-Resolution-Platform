import { EmptyState } from "@/components/ui/EmptyState";

export default function CustomersPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-950">Customers</h1>
      <EmptyState
        title="No customer view yet"
        description="Customer accounts and memory context will be added in the read-only console phase."
      />
    </div>
  );
}
