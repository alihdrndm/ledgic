import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Gallery } from "./Gallery";

// Folder is "%5Fsystem" so the route is /_system (a plain "_system" folder is private in the App Router).
export const metadata: Metadata = { title: "System", robots: { index: false } };

export default function SystemPage() {
  if (process.env.NODE_ENV === "production" && process.env.LEDGIC_SHOW_SYSTEM !== "1") notFound();
  return <Gallery />;
}
