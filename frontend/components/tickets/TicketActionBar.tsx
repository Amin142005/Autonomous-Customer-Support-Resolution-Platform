"use client";

import { FormEvent, useState } from "react";
import { api } from "@/lib/api";
import type { ApprovalDecisionRequest } from "@/lib/types";

interface TicketActionBarProps {
  ticketId: string;
  canAct: boolean;
  approvalId?: string;
  approvalStatus?: string;
  onUpdated?: () => void;
}

export function TicketActionBar({
  ticketId,
  canAct,
  approvalId,
  approvalStatus,
  onUpdated,
}: TicketActionBarProps) {
  const [body, setBody] = useState("");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const run = async (operation: () => Promise<unknown>) => {
    if (!canAct) return;
    setSubmitting(true);
    setMessage(null);
    try {
      await operation();
      setMessage("Action completed");
      onUpdated?.();
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Action failed");
    } finally {
      setSubmitting(false);
    }
  };

  const submitReply = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!body.trim()) return;
    void run(() => api.replyToTicket(ticketId, { body }));
  };

  const submitEscalation = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!reason.trim()) return;
    void run(() => api.escalateTicket(ticketId, { body: reason }));
  };

  const approve = () => {
    if (!approvalId || approvalStatus !== "pending") return;
    const decision: ApprovalDecisionRequest = {};
    void run(() => api.approve(approvalId, decision));
  };

  const reject = () => {
    if (!approvalId || approvalStatus !== "pending") return;
    const decision: ApprovalDecisionRequest = {};
    void run(() => api.reject(approvalId, decision));
  };

  return (
    <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-semibold text-slate-950">Ticket actions</h2>
        {approvalStatus === "pending" && approvalId ? (
          <span className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-800">
            Approval pending
          </span>
        ) : null}
      </div>

      {message ? (
        <p
          role="status"
          className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600"
        >
          {message}
        </p>
      ) : null}

      {approvalStatus === "pending" && approvalId ? (
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={approve}
            disabled={!canAct || submitting}
            className="rounded-lg bg-emerald-700 px-3 py-2 text-sm font-semibold text-white disabled:bg-slate-300"
          >
            Approve
          </button>
          <button
            type="button"
            onClick={reject}
            disabled={!canAct || submitting}
            className="rounded-lg border border-red-300 text-red-700 px-3 py-2 text-sm font-semibold disabled:text-slate-400"
          >
            Reject
          </button>
        </div>
      ) : null}

      <form onSubmit={submitReply} className="space-y-2">
        <label
          htmlFor="reply-body"
          className="text-xs font-semibold uppercase text-slate-500"
        >
          Customer reply
        </label>
        <textarea
          id="reply-body"
          value={body}
          onChange={(event) => setBody(event.target.value)}
          disabled={!canAct || submitting}
          rows={3}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-50"
        />
        <div className="grid grid-cols-2 gap-2">
          <button
            type="submit"
            disabled={!canAct || submitting || !body.trim()}
            className="rounded-lg bg-brand px-3 py-2 text-sm font-semibold text-white disabled:bg-slate-300"
          >
            Send reply
          </button>
          <button
            type="button"
            onClick={() => {
              if (!body.trim()) return;
              void run(() => api.requestTicketInfo(ticketId, { body }));
            }}
            disabled={!canAct || submitting || !body.trim()}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold disabled:text-slate-400"
          >
            Request info
          </button>
        </div>
      </form>

      <form onSubmit={submitEscalation} className="space-y-2">
        <label
          htmlFor="escalation-reason"
          className="text-xs font-semibold uppercase text-slate-500"
        >
          Escalation reason
        </label>
        <textarea
          id="escalation-reason"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          disabled={!canAct || submitting}
          rows={2}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-50"
        />
        <button
          type="submit"
          disabled={!canAct || submitting || !reason.trim()}
          className="w-full rounded-lg border border-red-300 px-3 py-2 text-sm font-semibold text-red-700 disabled:text-slate-400"
        >
          Escalate ticket
        </button>
      </form>

      {!canAct ? (
        <p className="text-xs text-slate-500">
          Viewer users can inspect this ticket but cannot perform actions.
        </p>
      ) : null}
    </section>
  );
}
