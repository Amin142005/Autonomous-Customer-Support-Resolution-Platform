import { Suspense } from "react";
import { LoginForm } from "@/components/auth/LoginForm";

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-canvas px-4">
      <Suspense
        fallback={
          <div className="rounded-xl border border-slate-200 bg-white px-6 py-5 text-sm text-slate-600">
            Loading sign-in...
          </div>
        }
      >
        <LoginForm />
      </Suspense>
    </main>
  );
}
