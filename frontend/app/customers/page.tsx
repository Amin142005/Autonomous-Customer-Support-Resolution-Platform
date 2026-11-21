"use client";

import Link from "next/link";
import { useCallback } from "react";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/hooks";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingState } from "@/components/ui/LoadingState";
import { NetworkErrorBanner } from "@/components/ui/NetworkErrorBanner";
import { PageHeader } from "@/components/ui/PageHeader";

export default function CustomersPage() {
  const loader = useCallback(() => api.listCustomers({ limit: 100 }), []);
  const { data, loading, error, reload } = usePolling(loader, 10000);

  if (loading) return <LoadingState label="Loading customers..." />;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Accounts"
        title="Customers"
        description="Read-only customer account and support context."
      />
      {error ? (
        <NetworkErrorBanner message={error} onRetry={() => void reload()} />
      ) : null}

      {data?.items.length ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {data.items.map((customer) => (
            <Link
              key={customer.id}
              href={`/customers/${customer.id}`}
              className="rounded-xl border border-slate-200 bg-white p-5 hover:border-slate-300"
            >
              <p className="font-semibold text-slate-950">{customer.name}</p>
              <p className="mt-1 text-sm text-slate-500">{customer.email}</p>
              <div className="mt-4 flex gap-2 text-xs text-slate-500">
                {customer.company ? <span>{customer.company}</span> : null}
                {customer.plan ? (
                  <span className="rounded-full bg-slate-100 px-2 py-1">
                    {customer.plan}
                  </span>
                ) : null}
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <EmptyState
          title="No customers"
          description="No customer accounts are available in the CloudDesk API."
        />
      )}
    </div>
  );
}
