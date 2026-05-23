import { healthColor } from "@/lib/utils";

interface Props {
  score:  number; // 0-100
  size?:  number;
  stroke?: number;
  label?: string;
}

export function ProgressRing({ score, size = 48, stroke = 3, label }: Props) {
  const r  = (size - stroke * 2) / 2;
  const cx = size / 2;
  const c  = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, score));
  const offset = c - (pct / 100) * c;
  const color = healthColor(score);

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={cx} cy={cx} r={r} fill="none" stroke="#1e2330" strokeWidth={stroke} />
        <circle cx={cx} cy={cx} r={r} fill="none" stroke={color} strokeWidth={stroke}
          strokeDasharray={c} strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 0.4s ease" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-mono text-xs font-semibold leading-none" style={{ color }}>
          {label ?? score}
        </span>
      </div>
    </div>
  );
}
