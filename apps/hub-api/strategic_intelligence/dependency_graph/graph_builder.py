"""
Cross-BU workflow dependency graph.

Nodes: proposals, stakeholders, BUs.
Edges: assignment, approval dependency, BU coupling.

Detects: critical path delays, blocked workflows, approval chokepoints,
high-risk stakeholders (single points of failure).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class GraphNode:
    node_id: str
    node_type: str              # proposal | stakeholder | bu
    label: str
    metadata: dict = field(default_factory=dict)


@dataclass
class GraphEdge:
    source_id: str
    target_id: str
    edge_type: str              # assigned_to | approves | blocks | depends_on | cross_bu
    weight: float = 1.0        # strength/criticality
    metadata: dict = field(default_factory=dict)


@dataclass
class CriticalPathNode:
    entity_id: str
    entity_type: str
    label: str
    dependency_count: int
    is_bottleneck: bool
    rationale: str


@dataclass
class DependencyGraph:
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    critical_path: list[CriticalPathNode]
    chokepoints: list[dict]         # stakeholders blocking multiple proposals
    blocked_proposals: list[dict]   # proposals with all paths blocked
    cross_bu_dependencies: list[dict]
    high_risk_stakeholders: list[dict]
    summary: str
    generated_at: str


def build_dependency_graph(db: "Session") -> DependencyGraph:
    from sqlalchemy import select
    from models import Proposal, Approval
    from models.proposal import Assignment
    from models.stakeholder import Stakeholder
    from models.opportunity import Opportunity

    now = datetime.now(timezone.utc)

    proposals = db.scalars(select(Proposal)).all()
    approvals = db.scalars(select(Approval)).all()
    assignments = db.scalars(select(Assignment)).all()
    stakeholders = db.scalars(select(Stakeholder)).all()

    opp_ids = [p.opportunity_id for p in proposals if p.opportunity_id]
    opp_map: dict[str, Opportunity] = {}
    if opp_ids:
        opps = db.scalars(select(Opportunity).where(Opportunity.id.in_(opp_ids))).all()
        opp_map = {o.id: o for o in opps}

    sme_map = {s.id: s for s in stakeholders}

    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    bu_set: set[str] = set()

    # Proposal nodes
    for p in proposals:
        opp = opp_map.get(p.opportunity_id or "")
        nodes.append(GraphNode(
            node_id=f"proposal:{p.id}",
            node_type="proposal",
            label=opp.title if opp else f"Proposal {p.id[:8]}",
            metadata={"stage": p.stage, "deal_value_cr": str(opp.deal_value_cr) if opp and opp.deal_value_cr else None},
        ))

    # Stakeholder nodes + BU tracking
    for s in stakeholders:
        bu = s.bu or "unassigned"
        bu_set.add(bu)
        nodes.append(GraphNode(
            node_id=f"stakeholder:{s.id}",
            node_type="stakeholder",
            label=s.name,
            metadata={"role": s.role, "bu": bu, "workload": s.current_workload},
        ))

    # BU nodes
    for bu in bu_set:
        nodes.append(GraphNode(
            node_id=f"bu:{bu}",
            node_type="bu",
            label=bu,
            metadata={},
        ))

    # Edges: SME assignment → proposal
    for a in assignments:
        edges.append(GraphEdge(
            source_id=f"stakeholder:{a.stakeholder_id}",
            target_id=f"proposal:{a.proposal_id}",
            edge_type="assigned_to",
            weight=1.0,
        ))
        # SME BU → proposal BU coupling
        s = sme_map.get(a.stakeholder_id)
        if s and s.bu:
            edges.append(GraphEdge(
                source_id=f"bu:{s.bu}",
                target_id=f"proposal:{a.proposal_id}",
                edge_type="depends_on",
                weight=0.5,
            ))

    # Edges: approver → approval → proposal
    stakeholder_approval_count: dict[str, int] = {}
    overdue_by_approver: dict[str, int] = {}

    for appr in approvals:
        if appr.approver_id:
            edges.append(GraphEdge(
                source_id=f"stakeholder:{appr.approver_id}",
                target_id=f"proposal:{appr.proposal_id}",
                edge_type="approves",
                weight=1.5 if appr.status == "pending" else 0.5,
                metadata={"status": appr.status, "stage": appr.stage},
            ))
            if appr.status == "pending":
                stakeholder_approval_count[appr.approver_id] = (
                    stakeholder_approval_count.get(appr.approver_id, 0) + 1
                )
                if appr.due_at:
                    due = appr.due_at.replace(tzinfo=timezone.utc) if appr.due_at.tzinfo is None else appr.due_at
                    if due < now:
                        overdue_by_approver[appr.approver_id] = (
                            overdue_by_approver.get(appr.approver_id, 0) + 1
                        )

    # Chokepoints: stakeholders blocking 3+ proposals
    chokepoints: list[dict] = []
    for sid, count in stakeholder_approval_count.items():
        if count >= 3:
            s = sme_map.get(sid)
            overdue = overdue_by_approver.get(sid, 0)
            chokepoints.append({
                "stakeholder_id": sid,
                "name": s.name if s else sid,
                "bu": s.bu if s else None,
                "blocked_proposals": count,
                "overdue_approvals": overdue,
                "severity": "critical" if overdue >= 2 else "high" if overdue >= 1 else "medium",
                "rationale": f"{s.name if s else sid} is blocking {count} proposals with {overdue} overdue.",
            })
    chokepoints.sort(key=lambda c: c["blocked_proposals"], reverse=True)

    # Blocked proposals: pending approvals with all overdue
    appr_by_proposal: dict[str, list] = {}
    for a in approvals:
        appr_by_proposal.setdefault(a.proposal_id, []).append(a)

    blocked_proposals: list[dict] = []
    for p in proposals:
        p_approvals = appr_by_proposal.get(p.id, [])
        if not p_approvals:
            continue
        pending = [a for a in p_approvals if a.status == "pending"]
        all_overdue = all(
            a.due_at and a.due_at.replace(tzinfo=timezone.utc) < now
            for a in pending
        ) if pending else False
        if all_overdue and pending:
            opp = opp_map.get(p.opportunity_id or "")
            blocked_proposals.append({
                "proposal_id": p.id,
                "stage": p.stage,
                "title": opp.title if opp else None,
                "overdue_approval_count": len(pending),
                "severity": "critical",
            })

    # Cross-BU dependencies: proposal assigned from multiple BUs
    proposal_bus: dict[str, set[str]] = {}
    for a in assignments:
        s = sme_map.get(a.stakeholder_id)
        if s and s.bu:
            proposal_bus.setdefault(a.proposal_id, set()).add(s.bu)

    cross_bu: list[dict] = []
    for pid, bus in proposal_bus.items():
        if len(bus) > 1:
            p = next((x for x in proposals if x.id == pid), None)
            opp = opp_map.get(p.opportunity_id or "") if p else None
            cross_bu.append({
                "proposal_id": pid,
                "title": opp.title if opp else None,
                "involved_bus": sorted(bus),
                "cross_bu_count": len(bus),
                "coordination_risk": "high" if len(bus) >= 3 else "medium",
            })
            # Add cross-BU dependency edges
            bus_list = sorted(bus)
            for i in range(len(bus_list) - 1):
                edges.append(GraphEdge(
                    source_id=f"bu:{bus_list[i]}",
                    target_id=f"bu:{bus_list[i+1]}",
                    edge_type="cross_bu",
                    weight=2.0,
                    metadata={"proposal_id": pid},
                ))

    # High-risk stakeholders: single point of failure (only assignee on high-value proposals)
    proposal_assignee_count: dict[str, int] = {}
    for a in assignments:
        proposal_assignee_count[a.proposal_id] = proposal_assignee_count.get(a.proposal_id, 0) + 1

    high_risk_smes: list[dict] = []
    solo_proposals: dict[str, list[str]] = {}
    for a in assignments:
        if proposal_assignee_count.get(a.proposal_id, 0) == 1:
            solo_proposals.setdefault(a.stakeholder_id, []).append(a.proposal_id)

    for sid, pids in solo_proposals.items():
        if len(pids) >= 2:
            s = sme_map.get(sid)
            high_risk_smes.append({
                "stakeholder_id": sid,
                "name": s.name if s else sid,
                "sole_assignee_on": len(pids),
                "risk": "If unavailable, {} proposal(s) lose their only assignee.".format(len(pids)),
            })

    # Critical path: proposals with most dependencies
    inbound: dict[str, int] = {}
    for e in edges:
        target = e.target_id
        inbound[target] = inbound.get(target, 0) + 1

    critical_path: list[CriticalPathNode] = []
    for node in nodes:
        dep_count = inbound.get(node.node_id, 0)
        if dep_count >= 3:
            is_bottleneck = any(
                c["stakeholder_id"] in node.node_id
                for c in chokepoints
            )
            critical_path.append(CriticalPathNode(
                entity_id=node.node_id,
                entity_type=node.node_type,
                label=node.label,
                dependency_count=dep_count,
                is_bottleneck=is_bottleneck,
                rationale=f"{dep_count} inbound dependencies — high coordination cost.",
            ))

    critical_path.sort(key=lambda c: c.dependency_count, reverse=True)

    summary = (
        f"Graph: {len(nodes)} nodes, {len(edges)} edges. "
        f"{len(chokepoints)} chokepoint(s), {len(blocked_proposals)} fully-blocked proposal(s), "
        f"{len(cross_bu)} cross-BU dependency relationship(s)."
    )

    return DependencyGraph(
        nodes=nodes,
        edges=edges,
        critical_path=critical_path[:10],
        chokepoints=chokepoints,
        blocked_proposals=blocked_proposals,
        cross_bu_dependencies=cross_bu,
        high_risk_stakeholders=high_risk_smes,
        summary=summary,
        generated_at=now.isoformat(),
    )
