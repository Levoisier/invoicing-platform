"use client";

import { useEffect, useState } from "react";

import Link from "next/link";

import { type InvoiceSummaryOut, api, fmtMoney } from "@/lib/api";
import { useAuthGuard } from "@/lib/use-auth-guard";

export default function InvoicesPage() {
  const ready = useAuthGuard();
  const [invoices, setInvoices] = useState<InvoiceSummaryOut[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (ready) {
      api
        .listInvoices()
        .then(setInvoices)
        .catch((e) => setError(String(e.message ?? e)));
    }
  }, [ready]);

  if (!ready) return null;

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center" }}>
        <h1 style={{ flex: 1 }}>Invoices</h1>
        <Link href="/invoices/new">
          <button>New invoice</button>
        </Link>
      </div>

      {error && <p className="error">{error}</p>}

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Status</th>
              <th className="num">Total</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {invoices.map((inv) => (
              <tr key={inv.id}>
                <td>{inv.number}</td>
                <td>
                  <span className={`badge ${inv.status}`}>{inv.status}</span>
                </td>
                <td className="num">{fmtMoney(inv.total)}</td>
                <td className="num">
                  <Link href={`/invoices/${inv.id}`}>View</Link>
                </td>
              </tr>
            ))}
            {invoices.length === 0 && (
              <tr>
                <td colSpan={4}>No invoices yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
