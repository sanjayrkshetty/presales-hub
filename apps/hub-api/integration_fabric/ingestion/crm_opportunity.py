"""CRM opportunity ingestion pipeline — Salesforce / HubSpot → internal Opportunity."""
from __future__ import annotations

import uuid
from decimal import Decimal
from integration_fabric.ingestion.pipeline import IngestionPipeline


class CRMOpportunityPipeline(IngestionPipeline):
    PIPELINE_NAME = "crm_opportunity"
    SUPPORTED_SOURCES = ["salesforce", "hubspot"]

    def validate(self, raw: dict) -> tuple[bool, list[str]]:
        errors = []
        if not isinstance(raw, dict):
            return False, ["Input must be a dict"]
        if not raw.get("records"):
            errors.append("Missing 'records' list")
        if not raw.get("source"):
            errors.append("Missing 'source' (salesforce|hubspot)")
        return not errors, errors

    def extract(self, raw: dict) -> list[dict]:
        source = raw["source"]
        extracted = []
        for rec in raw.get("records", []):
            if source == "salesforce":
                extracted.append({
                    "external_id": rec.get("Id", ""),
                    "name": rec.get("Name", ""),
                    "amount": rec.get("Amount", 0),
                    "stage": rec.get("StageName", ""),
                    "close_date": rec.get("CloseDate", ""),
                    "account": rec.get("Account", {}).get("Name", ""),
                    "source": "salesforce",
                })
            elif source == "hubspot":
                props = rec.get("properties", {})
                extracted.append({
                    "external_id": rec.get("id", ""),
                    "name": props.get("dealname", ""),
                    "amount": float(props.get("amount", 0) or 0),
                    "stage": props.get("dealstage", ""),
                    "close_date": props.get("closedate", ""),
                    "account": "",
                    "source": "hubspot",
                })
        return extracted

    def normalize(self, records: list[dict]) -> list[dict]:
        stage_map = {
            "Prospecting": "intake", "Qualification": "qualification",
            "Value Proposition": "proposal_review", "Id. Decision Makers": "approval",
            "Perception Analysis": "technical_review", "Proposal/Price Quote": "proposal_review",
            "Negotiation/Review": "approval", "Closed Won": "closed_won", "Closed Lost": "closed_lost",
            "appointmentscheduled": "intake", "qualifiedtobuy": "qualification",
            "presentationscheduled": "proposal_review", "decisionmakerboughtin": "approval",
            "contractsent": "approval", "closedwon": "closed_won", "closedlost": "closed_lost",
        }
        return [{
            "type": "crm_opportunity",
            "internal_id": str(uuid.uuid4()),
            "external_id": r["external_id"],
            "title": r["name"],
            "deal_value_cr": round(float(r["amount"] or 0) / 1e6, 3),
            "stage": stage_map.get(r["stage"], "intake"),
            "close_date": r["close_date"],
            "client_name": r["account"],
            "source": r["source"],
        } for r in records]

    def route(self, normalized: list[dict], db=None) -> list[str]:
        return [r["internal_id"] for r in normalized]
