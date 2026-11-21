import { cn } from "@/lib/cn";
import { formatLabel } from "@/lib/format";

interface StatusPillProps {
  value: string;
  tone?: "neutral" | "success" | "warning" | "danger";
}

export function StatusPill({ value, tone }: StatusPillProps) {
  const normalized = value.toLowerCase();
  const resolvedTone =
    tone ??
    (normalized.includes("resolved") ||
    normalized.includes("completed") ||
    normalized.includes("approved")
      ? "success"
      : normalized.includes("waiting") ||
          normalized.includes("pending") ||
          normalized.includes("paused")
        ? "warning"
        : normalized.includes("critical") ||
            normalized.includes("escalated") ||
            normalized.includes("rejected")
          ? "danger"
          : "neutral");

  const tones = {
    neutral: "border-slate-200 bg-slate-100 text-slate-700",
    success: "border-emerald-200 bg-emerald-50 text-emerald-700",
    warning: "border-amber-200 bg-amber-50 text-amber-800",
    danger: "border-red-200 bg-red-50 text-red-700",
  };

  return (
    <span
      className={cn(
        "inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold",
        tones[resolvedTone],
      )}
    >
      {formatLabel(value)}
    </span>
  );
}
