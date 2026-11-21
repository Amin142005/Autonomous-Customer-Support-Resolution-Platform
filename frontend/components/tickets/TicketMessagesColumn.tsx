"use client";

import { formatDate } from "@/lib/format";
import type { TicketMessage } from "@/lib/types";

interface TicketMessagesColumnProps {
  messages: TicketMessage[];
  canCompose?: boolean;
}

export function TicketMessagesColumn({
  messages,
  canCompose = false,
}: TicketMessagesColumnProps) {
  return (
    <section className="flex min-h-[620px] flex-col overflow-hidden rounded-xl border border-slate-200 bg-white">
      <header className="border-b border-slate-200 px-5 py-4">
        <h2 className="font-semibold text-slate-950">Messages</h2>
      </header>

      <div className="flex-1 divide-y divide-slate-100 overflow-y-auto">
        {messages.length ? (
          messages.map((message) => (
            <article key={message.id} className="px-5 py-4">
              <div className="flex justify-between gap-3 text-xs text-slate-500">
                <span className="font-semibold capitalize">
                  {message.author_type}
                </span>
                <time dateTime={message.created_at}>
                  {formatDate(message.created_at)}
                </time>
              </div>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">
                {message.body}
              </p>
            </article>
          ))
        ) : (
          <p className="px-5 py-8 text-sm text-slate-500">No messages.</p>
        )}
      </div>

      <div className="border-t border-slate-200 p-4">
        <label
          className="block text-xs font-semibold uppercase text-slate-500"
          htmlFor="ticket-message"
        >
          Reply or internal note
        </label>
        <textarea
          id="ticket-message"
          rows={3}
          disabled={!canCompose}
          placeholder={
            canCompose
              ? "Write a customer reply..."
              : "Action controls are available to agent roles"
          }
          className="mt-2 w-full resize-none rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-50 disabled:text-slate-400"
        />
        <button
          type="button"
          disabled={!canCompose}
          className="mt-3 w-full rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          Send reply
        </button>
      </div>
    </section>
  );
}
