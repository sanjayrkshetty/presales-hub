"use client";
import { useState } from "react";
import { ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { Spinner } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import type { ReactNode } from "react";

export interface Column<T> {
  key:       string;
  label:     string;
  sortable?: boolean;
  align?:    "left" | "right" | "center";
  render?:   (row: T) => ReactNode;
  className?: string;
}

interface Props<T> {
  columns:      Column<T>[];
  rows:         T[];
  rowKey:       (row: T) => string;
  isLoading?:   boolean;
  emptyTitle?:  string;
  emptyMessage?: string;
  onRowClick?:  (row: T) => void;
  className?:   string;
}

export function DataTable<T>({
  columns, rows, rowKey, isLoading, emptyTitle = "No data", emptyMessage, onRowClick, className,
}: Props<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  function handleSort(key: string) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  }

  const sorted = [...rows].sort((a, b) => {
    if (!sortKey) return 0;
    const av = (a as Record<string, unknown>)[sortKey];
    const bv = (b as Record<string, unknown>)[sortKey];
    const cmp = String(av ?? "").localeCompare(String(bv ?? ""), undefined, { numeric: true });
    return sortDir === "asc" ? cmp : -cmp;
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Spinner size="md" />
      </div>
    );
  }

  if (rows.length === 0) {
    return <EmptyState title={emptyTitle} message={emptyMessage} />;
  }

  return (
    <div className={cn("overflow-x-auto", className)}>
      <table className="data-table w-full text-xs font-mono" role="table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                className={cn(
                  "text-2xs uppercase tracking-wider text-text-muted font-sans font-semibold py-2 px-3",
                  col.align === "right" && "text-right",
                  col.align === "center" && "text-center",
                  col.sortable && "cursor-pointer select-none hover:text-text-primary"
                )}
                aria-sort={
                  sortKey === col.key ? (sortDir === "asc" ? "ascending" : "descending") : undefined
                }
                onClick={col.sortable ? () => handleSort(col.key) : undefined}
              >
                <span className="inline-flex items-center gap-1">
                  {col.label}
                  {col.sortable && (
                    sortKey === col.key ? (
                      sortDir === "asc" ? <ArrowUp size={9} /> : <ArrowDown size={9} />
                    ) : (
                      <ArrowUpDown size={9} className="opacity-40" />
                    )
                  )}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr
              key={rowKey(row)}
              className={cn(
                "border-b border-border/40 transition-colors",
                onRowClick ? "cursor-pointer hover:bg-white/3" : "hover:bg-white/2"
              )}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
            >
              {columns.map((col) => (
                <td
                  key={col.key}
                  className={cn(
                    "py-2 px-3 text-text-secondary",
                    col.align === "right" && "text-right",
                    col.align === "center" && "text-center",
                    col.className
                  )}
                >
                  {col.render
                    ? col.render(row)
                    : String((row as Record<string, unknown>)[col.key] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
