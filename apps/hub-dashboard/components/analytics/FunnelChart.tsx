import dynamic from "next/dynamic";
import { ChartSkeleton } from "@/components/ui/ChartSkeleton";
import type { FunnelStage } from "@/lib/types/api";

const FunnelChartInner = dynamic(
  () => import("./FunnelChartInner").then((m) => ({ default: m.FunnelChartInner })),
  { ssr: false, loading: () => <ChartSkeleton height={220} /> }
);

export function FunnelChart({ stages }: { stages: FunnelStage[] }) {
  return <FunnelChartInner stages={stages} />;
}
