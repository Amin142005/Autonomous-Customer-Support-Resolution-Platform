"use client";

import Link from "next/link";
import { useCallback } from "react";
import { api } from "@/lib/api";
import { formatLabel } from "@/lib/format";
import { usePolling } from "@/lib/hooks";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingState } from "@/components/ui/LoadingState";
import { NetworkErrorBanner } from "@/components/ui/NetworkErrorBanner";
import { PageHeader } from "@/components/ui/PageHeader";

export default function KnowledgePage() {
  const loader = useCallback(() => api.listKnowledge(), []);
  const { data, loading, error, reload } = usePolling(loader, 30000);

  if (loading) return <LoadingState label="Loading knowledge articles..." />;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Approved support content"
        title="Knowledge"
        description="Read-only support articles available to agents and workflows."
      />
      {error ? (
        <NetworkErrorBanner message={error} onRetry={() => void reload()} />
      ) : null}

      {data?.items.length ? (
        <div className="grid gap-4 md:grid-cols-2">
          {data.items.map((article) => (
            <article
              key={article.id}
              className="rounded-xl border border-slate-200 bg-white p-5"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase text-brand">
                    {formatLabel(article.category)}
                  </p>
                  <h2 className="mt-2 font-semibold text-slate-950">
                    {article.title}
                  </h2>
                </div>
                <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
                  {article.slug}
                </span>
              </div>
              <p className="mt-3 text-sm leading-6 text-slate-600">
                {article.summary}
              </p>
              <Link
                href={`/knowledge/${article.id}`}
                className="mt-4 inline-block text-sm font-semibold text-brand hover:underline"
              >
                Read article
              </Link>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState
          title="No knowledge articles"
          description="No approved articles are available from the knowledge service."
        />
      )}
    </div>
  );
}
