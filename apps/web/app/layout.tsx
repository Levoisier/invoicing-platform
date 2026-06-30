import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";
import { Nav } from "./nav";

export const metadata: Metadata = {
  title: "Invoicing Platform",
  description: "Self-hostable invoicing with a pluggable tax engine.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Nav />
        <main className="container">{children}</main>
      </body>
    </html>
  );
}
