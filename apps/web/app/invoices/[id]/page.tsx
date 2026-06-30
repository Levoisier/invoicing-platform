"use client";

import { type FormEvent, useCallback, useEffect, useState } from "react";

import { useParams } from "next/navigation";

import { type InvoiceOut, api, fmtMoney } from "@/lib/api";
import { useAuthGuard } from "@/lib/use-auth-guard";

export default function InvoiceDetailPage() {
  const ready = useAuthGuard();
  // useParams (not the async `params` prop) because this is a client component.
  const params = useParams<{ id: string }>();
  const id = Number(params.id);

  const [invoice, setInvoice] = useState<InvoiceOut | null>(null);
  const [amount, setAmount] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .getInvoice(id)
      .then(setInvoice)
      .catch((e) => setError(String(e.message ?? e)));
  }, [id]);

  useEffect(() => {
    if (ready) load();
  }, [ready, load]);

  async function pay(e: FormEvent) {
    e.preventDefault();
    if (!invoice) return;
    setError(null);
    try {
      await api.recordPayment(invoice.id, { amount, currency: invoice.currency });
      setAmount("");
      load(); // re-fetch so the status badge reflects the new state
    } catch (e) {
      setError(String((e as Error).message));
    }
  }

  if (!ready) return null;
  if (!invoice) return <p>{error ?? "Loading…"}</p>;

  return (
    <div>
      <h1>
        Invoice #{invoice.number} <span className={`badge ${invoice.status}`}>{invoice.status}</span>
      </h1>

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Description</th>
              <th className="num">Qty</th>
              <th className="num">Unit price</th>
              <th>Tax</th>
              <th className="num">Net</th>
            </tr>
          </thead>
          <tbody>
            {invoice.lines.map((l, i) => (
              <tr key={i}>
                <td>{l.description}</td>
                <td className="num">{String(l.quantity)}</td>
                <td className="num">{String(l.unit_price)}</td>
                <td>{l.tax_code}</td>
                <td className="num">{fmtMoney(l.net)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p>Subtotal: {fmtMoney(invoice.subtotal)}</p>
        <p>IVA: {fmtMoney(invoice.tax)}</p>
        <p>
          <strong>Total: {fmtMoney(invoice.total)}</strong>
        </p>
        <button onClick={() => api.downloadPdf(invoice.id, invoice.number)}>Download PDF</button>
      </div>

      {invoice.status !== "paid" && (
        <div className="card">
          <h3>Record payment</h3>
          <form onSubmit={pay}>
            <label>Amount ({invoice.currency})</label>
            <input value={amount} onChange={(e) => setAmount(e.target.value)} />
            {error && <p className="error">{error}</p>}
            <div style={{ marginTop: 12 }}>
              <button type="submit">Record payment</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
