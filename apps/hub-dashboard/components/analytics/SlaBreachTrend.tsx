import dynamic from "next/dynamic";
import { ChartSkeleton } from "@/components/ui/ChartSkeleton";
import type { SlaAnalytics } from "@/lib/types/api";

const SlaBreachTrendInner = dynamic(
  () => import("./SlaBreachTrendInner").then((m) => ({ default: m.SlaBreachTrendInner })),
  { ssr: false, loading: () => <ChartSkeleton height={180} /> }
);

export function SlaBreachTrend({ sla }: { sla: SlaAnalytics }) {
  return <SlaBreachTrendInner sla={sla} />;
}
