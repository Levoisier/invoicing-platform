import { redirect } from "next/navigation";

// The app has no dashboard yet; invoices is the natural landing screen.
export default function Home() {
  redirect("/invoices");
}
