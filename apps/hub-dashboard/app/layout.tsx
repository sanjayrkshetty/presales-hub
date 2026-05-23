import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { QueryProvider } from "@/providers/QueryProvider";
import { AppShell } from "@/components/layout/AppShell";
import { PageErrorBoundary } from "@/components/ui/ErrorBoundary";
import "./globals.css";

const inter = Inter({
  subsets:  ["latin"],
  variable: "--font-inter",
  display:  "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets:  ["latin"],
  variable: "--font-mono",
  display:  "swap",
  weight:   ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title:       "Presales Hub",
  description: "Enterprise AI-Native Presales Operating System",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <body>
        <QueryProvider>
          <PageErrorBoundary>
            <AppShell>
              {children}
            </AppShell>
          </PageErrorBoundary>
        </QueryProvider>
      </body>
    </html>
  );
}
