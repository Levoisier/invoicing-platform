// The typed API client. Every request/response type below is pulled from the
// GENERATED `types.ts` (B13), so if a backend contract changes and `make gen-types`
// is re-run, the mismatch shows up here as a TypeScript error — that's the whole
// point of generating the contract rather than hand-writing it.
import type { components } from "./types";

type Schemas = components["schemas"];
export type ClientIn = Schemas["ClientIn"];
export type ClientOut = Schemas["ClientOut"];
export type InvoiceIn = Schemas["InvoiceIn"];
export type InvoiceOut = Schemas["InvoiceOut"];
export type InvoiceSummaryOut = Schemas["InvoiceSummaryOut"];
export type LineIn = Schemas["LineIn"];
export type MoneyOut = Schemas["MoneyOut"];
export type PaymentIn = Schemas["PaymentIn"];
export type PaymentOut = Schemas["PaymentOut"];

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "invoicing.token";

// Token lives in localStorage: simple for a single-user dev tool. (A hardened
// build would use an httpOnly cookie; out of v1 scope.)
export const session = {
  get token(): string | null {
    return typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY);
  },
  set(token: string) {
    localStorage.setItem(TOKEN_KEY, token);
  },
  clear() {
    localStorage.removeItem(TOKEN_KEY);
  },
};

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

function authHeaders(extra?: HeadersInit): Headers {
  const headers = new Headers(extra);
  const token = session.token;
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return headers;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = authHeaders(init.headers);
  if (init.body) headers.set("Content-Type", "application/json");
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      // non-JSON error body; keep the status text
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  async login(username: string, password: string): Promise<void> {
    const res = await fetch(`${BASE}/auth/token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) throw new ApiError(res.status, "invalid credentials");
    const data = (await res.json()) as Schemas["TokenOut"];
    session.set(data.access_token);
  },

  listClients: () => request<ClientOut[]>("/clients"),
  createClient: (body: ClientIn) =>
    request<ClientOut>("/clients", { method: "POST", body: JSON.stringify(body) }),

  listInvoices: () => request<InvoiceSummaryOut[]>("/invoices"),
  createInvoice: (body: InvoiceIn) =>
    request<InvoiceOut>("/invoices", { method: "POST", body: JSON.stringify(body) }),
  getInvoice: (id: number) => request<InvoiceOut>(`/invoices/${id}`),
  recordPayment: (id: number, body: PaymentIn) =>
    request<PaymentOut>(`/invoices/${id}/payments`, { method: "POST", body: JSON.stringify(body) }),

  // PDF needs the auth header, so a plain <a href> can't fetch it — we pull the
  // bytes with the token, then trigger a download from an object URL.
  async downloadPdf(id: number, number: number): Promise<void> {
    const res = await fetch(`${BASE}/invoices/${id}/pdf`, { headers: authHeaders() });
    if (!res.ok) throw new ApiError(res.status, "could not download PDF");
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download = `invoice-${number}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  },
};

export function fmtMoney(m: MoneyOut): string {
  // amount is a string (preserved Decimal); render with thousands separators and
  // no forced decimals, so COP shows as "COP 1,240,000".
  return `${m.currency} ${Number(m.amount).toLocaleString("en-US")}`;
}
