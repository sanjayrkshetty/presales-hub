# Presales Hub — Roadmap

> An AI-native operating system for the pre-sales lifecycle: discovery → scoping → proposal →
> approval, with durable workflows, real-time signals, and AI assistance throughout.

This document is the public point of view on where Presales Hub is and where it's going. It is
deliberately honest about current maturity — a roadmap that over-claims is worth less than one you
can trust.

---

## Why this exists

Pre-sales work in security and compliance services is high-context and deadline-bound: many
opportunities, multi-stage proposals, SME assignments, approval chains, and SLAs running in parallel.
Presales Hub models that lifecycle as durable, observable, AI-assisted workflows instead of
spreadsheets and email threads.

## Engineering principles

1. **Security is a feature, not a footnote.** Auth, RBAC, tenant isolation, and rate limiting are
   first-class and continuously red-teamed — including against our own assumptions.
2. **Durable over best-effort.** Proposal lifecycles run on Temporal so state survives restarts and
   every transition is auditable.
3. **Observable by default.** Correlation IDs, Prometheus metrics, and distributed traces are built
   in, not bolted on.
4. **Honest maturity.** Ship what works, document what doesn't, and keep the gap visible.

---

## Where it is today

**Foundation built and running locally** (FastAPI · Next.js · PostgreSQL · Redis · Temporal):

- Opportunity, proposal, approval, stakeholder, and analytics domains modelled end-to-end
- Durable proposal-lifecycle workflows on Temporal
- Real-time dashboard via WebSocket event streaming
- AI assistance surfaces (forecast, recommendations, copilot drafting)
- JWT auth with refresh-token rotation, account lockout, rate limiting, security headers
- Observability stack: health/readiness probes, Prometheus metrics, Jaeger traces

**Active hardening (in progress):** a structured security pass is underway across authentication
enforcement, the browser auth flow, and route-level authorization. Findings are being root-caused
and fixed with verification rather than patched over.

---

## Roadmap

### Now — Harden the foundation
- Enforce authentication and RBAC consistently across every API surface
- Close the cross-origin auth/session flow so reloads and real-time channels are reliable
- Verify each fix against real browser behaviour, not just request-level checks

### Next — Complete the product loops
- First-class proposal creation and stage advancement from the UI
- Surface SME assignment and the approval-decision flow as clear lifecycle actions
- Seed realistic approval and workflow data so the full lifecycle is demonstrable

### Later — Scale and depth
- Multi-tenant isolation with per-tenant quotas, validated end-to-end
- Deeper AI: proposal quality scoring, risk surfacing, win-probability calibration
- Production deployment path (TLS termination, blue/green, container orchestration)

---

## Non-goals (for now)

- Not a general CRM — it is opinionated around the pre-sales proposal lifecycle.
- Not chasing feature breadth ahead of correctness; depth and trustworthiness come first.

---

*Maintained by [Sanjay R K Shetty](https://github.com/sanjayrkshetty). Roadmap is a direction, not a
contract — it will evolve as the work does.*
