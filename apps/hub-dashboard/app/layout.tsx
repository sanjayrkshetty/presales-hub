import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Presales Hub",
  description: "Enterprise Presales Operating System",
};

const NAV = [
  { href: "/",             label: "Pipeline" },
  { href: "/analytics",   label: "Analytics" },
  { href: "/stakeholders",label: "Stakeholders" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen" style={{ background: "var(--bg-primary)" }}>
        <header className="border-b flex items-center gap-8 px-4 h-10 sticky top-0 z-50"
          style={{ borderColor: "var(--border)", background: "var(--bg-secondary)" }}>
          <span className="font-bold text-[11px] tracking-[0.2em] uppercase"
            style={{ color: "var(--accent)" }}>
            PRESALES HUB
          </span>
          <nav className="flex gap-1">
            {NAV.map(({ href, label }) => (
              <Link key={href} href={href}
                className="px-3 py-1 text-[11px] font-medium tracking-wider uppercase rounded transition-colors text-slate-400 hover:text-slate-200">
                {label}
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2 text-[10px]" style={{ color: "#64748b" }}>
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
            LIVE
          </div>
        </header>
        <main className="p-4">
          {children}
        </main>
      </body>
    </html>
  );
}
