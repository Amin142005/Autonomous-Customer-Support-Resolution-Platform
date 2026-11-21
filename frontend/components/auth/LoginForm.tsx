"use client";

import { FormEvent, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ApiError, NetworkError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const DEMO_USERS = [
  { email: "admin@clouddesk.demo", label: "Administrator" },
  { email: "sam.agent@clouddesk.demo", label: "Support agent" },
  { email: "vic.viewer@clouddesk.demo", label: "Read-only viewer" },
];

export function LoginForm() {
  const { signIn } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState(DEMO_USERS[1].email);
  const [error, setError] = useState<string | null>(
    searchParams.get("reason") === "expired"
      ? "Your CloudDesk session has expired. Please sign in again."
      : null,
  );
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      await signIn(email);
      router.replace("/dashboard");
    } catch (caught) {
      if (caught instanceof NetworkError) {
        setError(
          "The CloudDesk API is unavailable. Check that the backend is running.",
        );
      } else if (caught instanceof ApiError) {
        setError(caught.message);
      } else {
        setError("Unable to sign in with this demo account.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-7 shadow-sm">
      <div className="mb-6 flex items-center">
        <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-brand text-sm font-bold text-white">
          CD
        </div>
        <div className="ml-3">
          <h1 className="text-xl font-semibold text-slate-950">CloudDesk</h1>
          <p className="text-sm text-slate-500">Support Console</p>
        </div>
      </div>

      {error ? (
        <div
          role="alert"
          className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
        >
          {error}
        </div>
      ) : null}

      <form onSubmit={submit} className="space-y-4">
        <label className="block text-sm font-medium text-slate-700">
          Demo account
          <select
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="mt-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-950"
            disabled={submitting}
          >
            {DEMO_USERS.map((user) => (
              <option key={user.email} value={user.email}>
                {user.label} — {user.email}
              </option>
            ))}
          </select>
        </label>

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-lg bg-brand px-4 py-2.5 text-sm font-semibold text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? "Signing in..." : "Sign in"}
        </button>
      </form>
    </section>
  );
}
