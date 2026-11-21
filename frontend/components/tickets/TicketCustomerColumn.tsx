import { formatLabel } from "@/lib/format";
import type { TicketDetail } from "@/lib/types";

interface TicketCustomerColumnProps {
  ticket: TicketDetail;
}

export function TicketCustomerColumn({ ticket }: TicketCustomerColumnProps) {
  return (
    <aside className="space-y-4">
      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="font-semibold text-slate-950">Customer</h2>
        <p className="mt-3 font-medium text-slate-700">
          {ticket.customer.name}
        </p>
        <p className="mt-1 break-all text-sm text-slate-500">
          {ticket.customer.email}
        </p>
        {ticket.customer.company ? (
          <p className="mt-3 text-sm text-slate-600">
            {ticket.customer.company}
          </p>
        ) : null}
        {ticket.customer.plan ? (
          <span className="mt-3 inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">
            {ticket.customer.plan}
          </span>
        ) : null}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="font-semibold text-slate-950">Ticket</h2>
        <dl className="mt-3 space-y-3 text-sm">
          <div>
            <dt className="text-slate-500">Category</dt>
            <dd className="mt-1 font-medium">{formatLabel(ticket.category)}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Channel</dt>
            <dd className="mt-1 font-medium">{formatLabel(ticket.channel)}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Workspace</dt>
            <dd className="mt-1 font-medium">
              {ticket.workspace?.name ?? "—"}
            </dd>
          </div>
          <div>
            <dt className="text-slate-500">Ticket number</dt>
            <dd className="mt-1 font-medium">{ticket.number}</dd>
          </div>
        </dl>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="font-semibold text-slate-950">Original request</h2>
        <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-600">
          {ticket.body}
        </p>
      </section>
    </aside>
  );
}
