"use client";

import { useCallback } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { formatLabel } from "@/lib/format";
import { usePolling } from "@/lib/hooks";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingState } from "@/components/ui/LoadingState";
import { NetworkErrorBanner } from "@/components/ui/NetworkErrorBanner";
import { PageHeader } from "@/components/ui/PageHeader";

export default function KnowledgeDetailPage() {
  const params = useParams<{ id: string }>();
  const articleId = params.id;
  const loader = useCallback(
    () => api.getKnowledgeArticle(articleId),
    [articleId],
  );
  const { data, loading, error, reload } = usePolling(loader, 30000);

  if (loading) return <LoadingState label="Loading knowledge article..." />;

  return (
    <div className="space-y-6">
      {error ? (
        <NetworkErrorBanner message={error} onRetry={() => void reload()} />
      ) : null}
      {data ? (
        <>
          <PageHeader
            eyebrow={formatLabel(data.category)}
            title={data.title}
            description={data.summary}
          />
          <article className="rounded-xl border border-slate-200 bg-white p-6">
            <div className="mb-5 flex flex-wrap gap-2">
              {data.tags.map((tag) => (
                <span
                  key={tag}
                  className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600"
                >
                  {tag}
                </span>
              ))}
            </div>
            <div className="whitespace-pre-wrap text-sm leading-7 text-slate-700">
              {data.content}
            </div>
          </article>
        </>
      ) : (
        <EmptyState
          title="Article unavailable"
          description="The approved knowledge article could not be loaded."
        />
      )}
    </div>
  );
}
