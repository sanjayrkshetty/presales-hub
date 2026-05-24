"use client";

import { useState } from "react";
import { Download } from "lucide-react";

interface Props {
  url: string;
  filename?: string;
  label?: string;
}

export function ExportButton({ url, filename, label = "Export CSV" }: Props) {
  const [loading, setLoading] = useState(false);

  async function handleExport() {
    setLoading(true);
    try {
      const res = await fetch(url, { credentials: "include" });
      if (!res.ok) throw new Error("Export failed");
      const blob = await res.blob();
      const href = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = href;
      a.download = filename ?? "export.csv";
      a.click();
      URL.revokeObjectURL(href);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <button
      onClick={handleExport}
      disabled={loading}
      className="flex items-center gap-1.5 px-3 py-1.5 rounded border border-border bg-bg-tertiary text-xs text-text-secondary hover:text-text-primary hover:border-border-subtle transition-colors disabled:opacity-50"
    >
      <Download size={12} className={loading ? "animate-bounce" : ""} />
      {loading ? "Exporting…" : label}
    </button>
  );
}
