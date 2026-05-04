import Link from "next/link";
import type { Metadata } from "next";
import { HeaderNav } from "@/components/HeaderNav";
import "./globals.css";

export const metadata: Metadata = {
  title: "Codex Fashion Commerce",
  description: "Fashion ecommerce demo with semantic search and Codex assistants"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <header className="topbar">
            <div className="topbar-inner">
              <Link href="/" className="brand">
                Codex Fashion
              </Link>
              <HeaderNav />
            </div>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
