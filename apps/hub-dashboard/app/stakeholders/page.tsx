import { api } from "@/lib/api";

export const revalidate = 30;

export default async function StakeholdersPage() {
  const stakeholders = await api.stakeholders().catch(() => []);
  const smes = await api.smeLoad().catch(() => []);

  const smeMap = new Map(smes.map(s => [s.id, s]));

  const ROLE_COLOR: Record<string, string> = {
    presales_lead:      "#00d4aa",
    solution_architect: "#818cf8",
    sme:                "#f59e0b",
    security_reviewer:  "#ef4444",
    finance:            "#22c55e",
    legal:              "#64748b",
    delivery:           "#38bdf8",
  };

  return (
    <div className="space-y-4">
      <h1 className="text-[11px] font-semibold tracking-widest uppercase" style={{ color: "#64748b" }}>
        Stakeholders & Expertise
      </h1>

      <div className="grid grid-cols-3 gap-3">
        {stakeholders.map(s => {
          const load = smeMap.get(s.id);
          const pct = load?.utilization_pct ?? Math.min(100, s.current_workload * 25);
          const color = ROLE_COLOR[s.role] ?? "#64748b";
          const utilColor = pct >= 90 ? "var(--danger)" : pct >= 60 ? "var(--warn)" : "var(--success)";

          return (
            <div key={s.id} className="panel p-4 space-y-3">
              <div className="flex justify-between items-start">
                <div>
                  <div className="text-[13px] font-semibold" style={{ color: "#e2e8f0" }}>{s.name}</div>
                  <div className="text-[10px] mt-0.5" style={{ color: "#64748b" }}>{s.email ?? s.bu}</div>
                </div>
                <span className="badge"
                  style={{ background: `${color}15`, color, border: `1px solid ${color}33`, fontSize: "9px" }}>
                  {s.role.replace(/_/g, " ")}
                </span>
              </div>

              <div className="space-y-1">
                <div className="flex justify-between text-[10px]">
                  <span style={{ color: "#64748b" }}>Workload</span>
                  <span style={{ color: utilColor }}>{s.current_workload} / 4 active</span>
                </div>
                <div className="health-bar">
                  <div className="health-bar-fill" style={{ width: `${pct}%`, background: utilColor, height: "4px" }} />
                </div>
              </div>

              <div className="space-y-1">
                <div className="text-[10px] font-semibold tracking-wider" style={{ color: "#475569" }}>
                  EXPERTISE
                </div>
                <div className="flex flex-wrap gap-1">
                  {s.expertise.map(e => (
                    <span key={e} className="badge text-[9px]"
                      style={{ background: "#ffffff08", color: "#94a3b8", border: "1px solid #1e2128" }}>
                      {e}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
