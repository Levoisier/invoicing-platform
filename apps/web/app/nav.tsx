"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { session } from "@/lib/api";

export function Nav() {
  const router = useRouter();
  function logout() {
    session.clear();
    router.replace("/login");
  }
  return (
    <nav className="nav">
      <strong>Invoicing</strong>
      <Link href="/clients">Clients</Link>
      <Link href="/invoices">Invoices</Link>
      <span className="spacer" />
      <button className="secondary" onClick={logout}>
        Log out
      </button>
    </nav>
  );
}
