"""
Presales Hub — Load Tests (Locust)

Usage:
    pip install locust
    locust -f load_tests/locustfile.py --host http://localhost:8003

    # Headless mode:
    locust -f load_tests/locustfile.py --host http://localhost:8003 \
           --users 50 --spawn-rate 5 --run-time 60s --headless

Scenarios:
- ApiUser: unauthenticated health/metrics traffic
- AuthenticatedUser: full user journey (login → analytics → proposals → SLA)
- HeavyUser: constant-throughput integration client
- ConcurrentProposalUser: burst proposal creation (10 VUs)
- ApprovalStormUser: approval queue read+write loop (5 VUs)
- AICopilotUser: AI copilot assist endpoint (5 VUs, 4s think time)
"""
import random
import string
from locust import HttpUser, TaskSet, task, between, constant_throughput


class UnauthenticatedTasks(TaskSet):
    @task(5)
    def health_check(self):
        self.client.get("/api/health", name="/api/health")

    @task(2)
    def metrics_check(self):
        self.client.get("/metrics", name="/metrics")

    @task(1)
    def ready_check(self):
        self.client.get("/api/ready", name="/api/ready")


class AuthenticatedTasks(TaskSet):
    token: str = ""

    def on_start(self):
        credentials = [
            {"email": "arjun@sisa.demo",   "password": "Demo@1234"},
            {"email": "admin@presaleshub.io", "password": "Admin@1234"},
        ]
        cred = random.choice(credentials)
        with self.client.post("/auth/login", json=cred, catch_response=True, name="/auth/login") as res:
            if res.status_code == 200:
                self.token = res.json().get("access_token", "")
                res.success()
            else:
                res.failure(f"Login failed: {res.status_code}")

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    @task(10)
    def pipeline_analytics(self):
        self.client.get("/api/analytics/pipeline", headers=self._headers(), name="/api/analytics/pipeline")

    @task(8)
    def sla_analytics(self):
        self.client.get("/api/analytics/sla", headers=self._headers(), name="/api/analytics/sla")

    @task(6)
    def list_opportunities(self):
        self.client.get("/api/opportunities", headers=self._headers(), name="/api/opportunities")

    @task(4)
    def list_proposals(self):
        self.client.get("/api/proposals", headers=self._headers(), name="/api/proposals")

    @task(3)
    def list_approvals(self):
        self.client.get("/api/approvals", headers=self._headers(), name="/api/approvals")

    @task(2)
    def stakeholders(self):
        self.client.get("/api/stakeholders", headers=self._headers(), name="/api/stakeholders")

    @task(1)
    def ai_usage_summary(self):
        self.client.get("/api/ai/usage/summary", headers=self._headers(), name="/api/ai/usage/summary")

    @task(1)
    def refresh_token(self):
        self.client.post("/auth/refresh", name="/auth/refresh")


class ApiUser(HttpUser):
    """Unauthenticated health-check / monitoring traffic."""
    tasks = [UnauthenticatedTasks]
    wait_time = between(1, 3)
    weight = 1


class AuthenticatedUser(HttpUser):
    """Authenticated user simulating real dashboard usage."""
    tasks = [AuthenticatedTasks]
    wait_time = between(2, 8)
    weight = 4


class HeavyUser(HttpUser):
    """High-frequency API consumer (e.g., CI/CD pipeline, integration)."""
    tasks = [AuthenticatedTasks]
    wait_time = constant_throughput(2)  # 2 requests/second
    weight = 1


# ── Phase 11 — Extended scenarios ─────────────────────────────────────────────

PROPOSAL_STAGES = ["qualification", "scoping", "proposal", "negotiation", "closed"]
OPPORTUNITY_NAMES = ["Acme Corp Pen Test", "BankCo ISO 27001", "HealthPlus HIPAA", "RetailX PCI DSS"]


class ConcurrentProposalUser(HttpUser):
    """Burst-creates proposals to stress DB write path. 10 VUs recommended."""
    weight = 2
    wait_time = between(0.5, 2)
    _token: str = ""

    def on_start(self) -> None:
        cred = {"email": "arjun@sisa.demo", "password": "Demo@1234"}
        with self.client.post("/auth/login", json=cred, catch_response=True, name="/auth/login") as res:
            if res.status_code == 200:
                self._token = res.json().get("access_token", "")
                res.success()
            else:
                res.failure(f"Login failed: {res.status_code}")

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"} if self._token else {}

    @task(8)
    def create_proposal(self) -> None:
        suffix = "".join(random.choices(string.ascii_lowercase, k=5))
        payload = {
            "title": f"Load test proposal {suffix}",
            "opportunity_name": random.choice(OPPORTUNITY_NAMES),
            "stage": random.choice(PROPOSAL_STAGES),
            "value": random.randint(50_000, 500_000),
        }
        with self.client.post("/api/proposals", json=payload,
                              headers=self._headers(), catch_response=True,
                              name="/api/proposals [create]") as res:
            if res.status_code in (200, 201):
                res.success()
            elif res.status_code == 422:
                res.failure(f"Validation error: {res.text[:200]}")
            else:
                res.failure(f"HTTP {res.status_code}")

    @task(2)
    def list_proposals(self) -> None:
        self.client.get("/api/proposals", headers=self._headers(), name="/api/proposals [list]")


class ApprovalStormUser(HttpUser):
    """Hammers the approval queue to expose lock contention. 5 VUs recommended."""
    weight = 1
    wait_time = between(0.2, 1)
    _token: str = ""

    def on_start(self) -> None:
        cred = {"email": "admin@presaleshub.io", "password": "Admin@1234"}
        with self.client.post("/auth/login", json=cred, catch_response=True, name="/auth/login") as res:
            if res.status_code == 200:
                self._token = res.json().get("access_token", "")
                res.success()
            else:
                res.failure(f"Admin login failed: {res.status_code}")

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"} if self._token else {}

    @task(6)
    def list_pending_approvals(self) -> None:
        self.client.get("/api/approvals?status=pending", headers=self._headers(),
                        name="/api/approvals [pending]")

    @task(3)
    def list_all_approvals(self) -> None:
        self.client.get("/api/approvals", headers=self._headers(),
                        name="/api/approvals [all]")

    @task(1)
    def create_approval_request(self) -> None:
        payload = {
            "proposal_id": random.randint(1, 100),
            "required_approvers": ["admin@presaleshub.io"],
            "approval_type": "standard",
        }
        with self.client.post("/api/approvals", json=payload,
                              headers=self._headers(), catch_response=True,
                              name="/api/approvals [create]") as res:
            if res.status_code in (200, 201, 404, 422):
                res.success()  # 404/422 acceptable — proposal may not exist
            else:
                res.failure(f"HTTP {res.status_code}")


class AICopilotUser(HttpUser):
    """Exercises the AI copilot endpoint with 4s think time. 5 VUs recommended."""
    weight = 1
    wait_time = between(4, 8)  # AI responses are slow; simulate reading time
    _token: str = ""

    SECTIONS = ["executive_summary", "scope_of_work", "pricing", "risk_mitigation", "timeline"]
    CONTEXTS = [
        "BFSI client, 500 endpoints, PCI DSS scope",
        "Healthcare startup, HIPAA readiness, 120 users",
        "E-commerce, ISO 27001 gap assessment, 3-month timeline",
    ]

    def on_start(self) -> None:
        cred = {"email": "arjun@sisa.demo", "password": "Demo@1234"}
        with self.client.post("/auth/login", json=cred, catch_response=True, name="/auth/login") as res:
            if res.status_code == 200:
                self._token = res.json().get("access_token", "")
                res.success()
            else:
                res.failure(f"Login failed: {res.status_code}")

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"} if self._token else {}

    @task
    def copilot_assist(self) -> None:
        payload = {
            "section": random.choice(self.SECTIONS),
            "context": random.choice(self.CONTEXTS),
            "proposal_id": random.randint(1, 50),
        }
        with self.client.post("/api/copilot/assist", json=payload,
                              headers=self._headers(), catch_response=True,
                              name="/api/copilot/assist",
                              timeout=30) as res:
            if res.status_code in (200, 201, 503):
                res.success()  # 503 = circuit breaker open, acceptable under load
            else:
                res.failure(f"HTTP {res.status_code}")
