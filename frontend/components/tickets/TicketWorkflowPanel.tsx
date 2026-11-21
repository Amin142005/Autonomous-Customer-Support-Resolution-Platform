"use client";

import { formatLabel } from "@/lib/format";
import type { WorkflowEvent, WorkflowStatusResponse } from "@/lib/types";
import { WorkflowSteps } from "./WorkflowSteps";

interface TicketWorkflowPanelProps {
  workflow: WorkflowStatusResponse | null;
  events: WorkflowEvent[];
  canAct?: boolean;
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

export function TicketWorkflowPanel({
  workflow,
  events,
  canAct = false,
}: TicketWorkflowPanelProps) {
  const state = workflow?.state ?? {};
  const evidence = asArray(state.evidence);
  const diagnosis = state.diagnosis as Record<string, unknown> | undefined;
  const resolution = state.resolution as Record<string, unknown> | undefined;
  const probableCauses = asArray(diagnosis?.probable_causes);
  const steps = asArray(diagnosis?.steps);
  const actions = asArray(resolution?.actions);
  const reply =
    typeof resolution?.customer_reply === "string"
      ? resolution.customer_reply
      : typeof resolution?.reply === "string"
        ? resolution.reply
        : "";

  return (
    <aside className="space-y-4">
      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex items-start justify-between gap-3">
          <h2 className="font-semibold text-slate-950">Workflow</h2>
          {workflow ? (
            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">
              {formatLabel(workflow.status)}
            </span>
          ) : null}
        </div>
        {workflow ? (
          <WorkflowSteps
            completedNodes={state.completed_nodes}
            currentNode={state.current_node}
          />
        ) : (
          <p className="mt-4 text-sm text-slate-500">
            No workflow has been started.
          </p>
        )}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="font-semibold text-slate-950">Evidence</h2>
        {evidence.length ? (
          <div className="mt-3 space-y-3">
            {evidence.slice(0, 5).map((item, index) => {
              const evidenceItem = item as Record<string, unknown>;
              return (
                <article
                  key={String(evidenceItem.id ?? index)}
                  className="rounded-lg border border-slate-200 p-3"
                >
                  <p className="text-sm font-medium text-slate-700">
                    {String(evidenceItem.title ?? "Knowledge evidence")}
                  </p>
                  {typeof evidenceItem.source === "string" ? (
                    <p className="mt-1 break-all text-xs text-brand">
                      {evidenceItem.source}
                    </p>
                  ) : null}
                  {typeof evidenceItem.snippet === "string" ? (
                    <p className="mt-2 text-xs leading-5 text-slate-500">
                      {evidenceItem.snippet}
                    </p>
                  ) : null}
                </article>
              );
            })}
          </div>
        ) : (
          <p className="mt-3 text-sm text-slate-500">
            Evidence will appear after the workflow retrieves knowledge.
          </p>
        )}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="font-semibold text-slate-950">Diagnosis</h2>
        {probableCauses.length || steps.length ? (
          <div className="mt-3 space-y-4 text-sm">
            {probableCauses.length ? (
              <div>
                <p className="font-medium text-slate-600">Probable causes</p>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-slate-600">
                  {probableCauses.map((cause, index) => (
                    <li key={index}>{String(cause)}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {steps.length ? (
              <div>
                <p className="font-medium text-slate-600">
                  Troubleshooting steps
                </p>
                <ol className="mt-2 list-decimal space-y-1 pl-5 text-slate-600">
                  {steps.map((step, index) => (
                    <li key={index}>{String(step)}</li>
                  ))}
                </ol>
              </div>
            ) : null}
          </div>
        ) : (
          <p className="mt-3 text-sm text-slate-500">
            Diagnosis will appear after troubleshooting.
          </p>
        )}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="font-semibold text-slate-950">Resolution and actions</h2>
        {actions.length ? (
          <div className="mt-3 space-y-2">
            {actions.map((action, index) => {
              const item = action as Record<string, unknown>;
              return (
                <div
                  key={index}
                  className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
                >
                  <p className="font-medium text-slate-700">
                    {String(item.tool ?? "Action")}
                  </p>
                  {Boolean(item.approval_required) ? (
                    <p className="mt-1 text-xs font-semibold text-amber-700">
                      Approval required
                    </p>
                  ) : (
                    <p className="mt-1 text-xs text-slate-500">
                      No approval required
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <p className="mt-3 text-sm text-slate-500">
            No proposed actions yet.
          </p>
        )}

        <label
          className="mt-4 block text-xs font-semibold uppercase text-slate-500"
          htmlFor="customer-reply"
        >
          Editable customer reply
        </label>
        <textarea
          id="customer-reply"
          rows={5}
          defaultValue={reply}
          disabled={!canAct}
          className="mt-2 w-full resize-none rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-50"
        />
      </section>

      {events.length ? (
        <section className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="font-semibold text-slate-950">Recent activity</h2>
          <div className="mt-3 space-y-2">
            {events
              .slice(-6)
              .reverse()
              .map((event) => (
                <div key={event.id} className="text-xs">
                  <p className="font-medium text-slate-700">
                    {formatLabel(event.event_type)}
                  </p>
                  {event.node_name ? (
                    <p className="mt-0.5 text-slate-500">
                      Node: {event.node_name}
                    </p>
                  ) : null}
                </div>
              ))}
          </div>
        </section>
      ) : null}
    </aside>
  );
}
