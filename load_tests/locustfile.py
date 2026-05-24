"""
Presales Hub — Load Tests (Locust)

Usage:
    pip install locust
    locust -f load_tests/locustfile.py --host http://localhost:8003

    # Headless mode:
    locust -f load_tests/locustfile.py --host http://localhost:8003 \
           --users 50 --spawn-rate 5 --run-time 60s --headless

Scenarios:
- ApiUser: unauthenticated API reads (health, metrics)
- AuthenticatedUser: full user journey (login → analytics → proposals → SLA)
"""
import random
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
