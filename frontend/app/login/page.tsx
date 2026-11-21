import { EmptyState } from "@/components/ui/EmptyState";

export default function LoginPage() {
  return (
    <div className="mx-auto max-w-lg py-12">
      <EmptyState
        title="Login"
        description="Demo authentication and role-aware sign-in will be added with the typed API client."
      />
    </div>
  );
}
