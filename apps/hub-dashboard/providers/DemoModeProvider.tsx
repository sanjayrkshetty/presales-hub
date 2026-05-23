"use client";

/**
 * DemoModeProvider — injects simulated live activity into the realtime store
 * and notification center so the dashboard feels alive even without a backend.
 *
 * Enabled when:  ?demo=1 URL param   OR   NEXT_PUBLIC_DEMO_MODE=true env var
 */
import { useEffect, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { useRealtimeStore } from "@/lib/store/realtime";
import { useNotificationStore } from "@/lib/store/notifications";
import type { ActivityEvent } from "@/lib/types/events";

const ACTORS = ["Arjun Kumar","Sneha Sharma","Rajiv Nair","Priya Singh","Vikram Mehta","System Monitor","AI Copilot"];
const PROPOSALS = ["P-HDFC-SOC","P-Infosys-ZT","P-Apollo-SIEM","P-DRDO-AI","P-Titan-Cloud","P-Flipkart-Comp"];
const ACTIONS: Array<ActivityEvent["action_type"]> = [
  "stage_transition","sme_assigned","approval_decision","created","created",
];
const DESCS = [
  "Stage advanced: technical review completed",
  "SME assigned for security architecture review",
  "AI Copilot generated executive summary",
  "Proposal health score updated to 88",
  "SLA checkpoint passed — on track for submission",
  "Approval request sent to finance team",
  "Risk score recalculated by decision engine",
  "Document version 3.2 uploaded",
  "SME availability confirmed — assignment accepted",
  "Stage transition validated by workflow engine",
  "Parallel review gate opened — 3 reviewers notified",
  "Commercial terms approved by presales lead",
];

const ALERT_DESCS = [
  "⚠ SLA warning: security review approaching 80% of allowed time",
  "⚠ Approval gate pending — deadline in 2h",
  "⚠ SME workload at capacity — assignment may delay",
];

const DEMO_NOTIFICATIONS = [
  { type: "danger" as const,  title: "SLA Breach Detected",      message: "Zero Trust Rollout — approval overdue by 1h. Escalating to Arjun Kumar." },
  { type: "warn"  as const,  title: "Workflow Stalled",          message: "SIEM Migration drafting has been in progress for 60+ hours." },
  { type: "info"  as const,  title: "AI Copilot Ready",          message: "Proposal draft for HDFC SOC Transformation is ready for review." },
  { type: "success" as const,title: "Approval Received",         message: "Karan Joshi approved the legal review for Zero Trust Rollout." },
  { type: "warn"  as const,  title: "Decision Engine Alert",     message: "Deal risk score for AI Governance Platform increased to 72 (was 50)." },
  { type: "info"  as const,  title: "New Opportunity Assigned",  message: "Cloud Modernization — Titan Industries added to your pipeline." },
];

let _eventSeq = 1000;

function makeEvent(isAlert: boolean): ActivityEvent {
  const actor = ACTORS[Math.floor(Math.random() * ACTORS.length)];
  const desc  = isAlert
    ? ALERT_DESCS[Math.floor(Math.random() * ALERT_DESCS.length)]
    : DESCS[Math.floor(Math.random() * DESCS.length)];
  return {
    event_type:  "activity",
    id:          `demo-${++_eventSeq}`,
    proposal_id: PROPOSALS[Math.floor(Math.random() * PROPOSALS.length)],
    actor_name:  actor,
    action_type: isAlert ? "sla_breach" : ACTIONS[Math.floor(Math.random() * ACTIONS.length)],
    description: desc,
    is_alert:    isAlert,
    created_at:  new Date().toISOString(),
  };
}

export function DemoModeProvider({ children }: { children: React.ReactNode }) {
  const searchParams  = useSearchParams();
  const pushEvent     = useRealtimeStore((s) => s.pushEvent);
  const addNote       = useNotificationStore((s) => s.addNotification);
  const injectedRef   = useRef(false);
  const intervalsRef  = useRef<number[]>([]);

  const enabled =
    searchParams.get("demo") === "1" ||
    process.env.NEXT_PUBLIC_DEMO_MODE === "true";

  useEffect(() => {
    if (!enabled || injectedRef.current) return;
    injectedRef.current = true;

    // Inject seed notifications immediately
    DEMO_NOTIFICATIONS.forEach((n) => addNote(n));

    // Inject a burst of historical activity events
    for (let i = 0; i < 12; i++) {
      setTimeout(() => pushEvent(makeEvent(i === 2 || i === 8)), i * 120);
    }

    // Ongoing trickle: ~1 event every 8–15 seconds
    const activityInterval = window.setInterval(() => {
      const isAlert = Math.random() < 0.12;
      pushEvent(makeEvent(isAlert));
      if (isAlert) {
        addNote({
          type:    "warn",
          title:   "SLA Alert",
          message: "A proposal is approaching its SLA deadline.",
        });
      }
    }, 8000 + Math.random() * 7000);

    // Occasional approval notifications
    const approvalInterval = window.setInterval(() => {
      addNote({
        type:    Math.random() > 0.5 ? "success" : "info",
        title:   Math.random() > 0.5 ? "Approval Received" : "Stage Advanced",
        message: DESCS[Math.floor(Math.random() * DESCS.length)],
      });
    }, 25000 + Math.random() * 15000);

    intervalsRef.current = [activityInterval, approvalInterval];

    return () => {
      intervalsRef.current.forEach((id) => clearInterval(id));
      intervalsRef.current = [];
    };
  }, [enabled, pushEvent, addNote]);

  return <>{children}</>;
}
