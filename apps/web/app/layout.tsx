import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import "./globals.css";
import { Nav } from "./nav";

export const metadata: Metadata = {
  title: "Invoicing Platform",
  description: "Self-hostable invoicing with a pluggable tax engine.",
};

// Mobile-first: tell the browser the page is dark so the chrome (status bar,
// address bar) matches and there's no white flash.
export const viewport: Viewport = {
  themeColor: "#000000",
  colorScheme: "dark",
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
