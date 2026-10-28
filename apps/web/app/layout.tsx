import type { Metadata, Viewport } from "next";
import { Archivo } from "next/font/google";
import { connection } from "next/server";
import "./globals.css";

const archivo = Archivo({
  subsets: ["latin"],
  weight: ["400", "600", "800"],
  display: "swap",
  variable: "--font-archivo",
});

export const metadata: Metadata = {
  title: { default: "Ledgic", template: "%s · Ledgic" },
  description: "Open-source accounts-payable automation: AI extraction, three-way match, agents, RAG and MCP.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  // Render per request: Next stamps the proxy's CSP nonce on its inline scripts only when dynamic.
  await connection();
  return (
    <html lang="en" className={archivo.variable}>
      <body>{children}</body>
    </html>
  );
}
