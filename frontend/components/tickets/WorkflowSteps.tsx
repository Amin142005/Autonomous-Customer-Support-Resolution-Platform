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
export type WorkflowStepStatus = "pending" | "current" | "completed";

export function deriveSteps(
  completedNodes: unknown,
  currentNode: unknown,
  runStatus: "running" | "paused" | "completed" | "waiting" = "waiting",
): Array<{ id: WorkflowStep; label: string; status: WorkflowStepStatus }> {
  const completed = new Set(
    Array.isArray(completedNodes)
      ? completedNodes.filter(
          (item): item is string => typeof item === "string",
        )
      : [],
  );
  const current = typeof currentNode === "string" ? currentNode : null;

  return WORKFLOW_STEPS.map((step) => {
    const isCompleted = completed.has(step);
    const isCurrent = current === step;

    let status: WorkflowStepStatus = "pending";
    if (isCompleted) status = "completed";
    if (isCurrent && runStatus !== "completed") status = "current";

    return {
      id: step,
      label: formatLabel(step),
      status,
    };
  });
}

export function deriveWorkflowRunStatus(
  workflowStatus: unknown,
  state: Record<string, unknown>,
): "running" | "paused" | "completed" | "waiting" {
  if (workflowStatus === "paused" || state.paused === true) return "paused";
  if (workflowStatus === "completed") return "completed";
  if (typeof workflowStatus === "string" && workflowStatus.length > 0) {
    return "running";
  }
  return "waiting";
}

interface WorkflowStepsProps {
  completedNodes?: unknown;
  currentNode?: unknown;
  runStatus?: "running" | "paused" | "completed" | "waiting";
}

export function WorkflowSteps({
  completedNodes,
  currentNode,
  runStatus = "waiting",
}: WorkflowStepsProps) {
  const steps = deriveSteps(completedNodes, currentNode, runStatus);

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
