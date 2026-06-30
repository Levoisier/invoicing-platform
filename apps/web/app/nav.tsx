"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { session } from "@/lib/api";
import { Logo } from "./logo";

export function Nav() {
  const router = useRouter();
  function logout() {
    session.clear();
    router.replace("/login");
  }
  return (
    <nav className="nav">
      <Link href="/" className="brand">
        <span className="mark">
          <Logo size={28} />
        </span>
        Invoicing
      </Link>
      <Link href="/clients">Clients</Link>
      <Link href="/invoices">Invoices</Link>
      <span className="spacer" />
      <button className="secondary" onClick={logout}>
        Log out
      </button>
    </nav>
  );
}
