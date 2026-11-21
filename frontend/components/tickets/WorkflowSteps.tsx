"use client";

import { cn } from "@/lib/cn";
import { formatLabel } from "@/lib/format";

export const WORKFLOW_STEPS = [
  "understand_ticket",
  "classify_severity",
  "customer_context",
  "knowledge_retrieval",
  "troubleshooting",
  "resolution_planning",
  "risk_check",
  "escalation",
  "human_approval",
  "execute_resolution",
  "ticket_summary",
  "memory_update",
] as const;

export type WorkflowStep = (typeof WORKFLOW_STEPS)[number];

export function deriveSteps(completedNodes: unknown, currentNode: unknown) {
  const completed = new Set(
    Array.isArray(completedNodes)
      ? completedNodes.filter(
          (item): item is string => typeof item === "string",
        )
      : [],
  );
  const current = typeof currentNode === "string" ? currentNode : null;

  return WORKFLOW_STEPS.map((step) => {
    const isCurrent = current === step;
    return {
      id: step,
      label: formatLabel(step),
      status: completed.has(step)
        ? isCurrent
          ? "current"
          : "completed"
        : isCurrent
          ? "current"
          : "pending",
    };
  });
}

interface WorkflowStepsProps {
  completedNodes?: unknown;
  currentNode?: unknown;
}

export function WorkflowSteps({
  completedNodes,
  currentNode,
}: WorkflowStepsProps) {
  const steps = deriveSteps(completedNodes, currentNode);

  return (
    <ol aria-label="Workflow steps" className="space-y-2">
      {steps.map((step, index) => (
        <li key={step.id} className="flex items-center gap-3">
          <span
            className={cn(
              "flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs font-semibold",
              step.status === "completed"
                ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                : step.status === "current"
                  ? "border-brand bg-brand text-white"
                  : "border-slate-200 bg-slate-50 text-slate-400",
            )}
            aria-hidden="true"
          >
            {index + 1}
          </span>
          <span
            className={cn(
              "text-sm",
              step.status === "pending"
                ? "text-slate-400"
                : "font-medium text-slate-700",
            )}
          >
            {step.label}
          </span>
        </li>
      ))}
    </ol>
  );
}
