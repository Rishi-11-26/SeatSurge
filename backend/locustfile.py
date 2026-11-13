"""
SeatSurge Locust Load & Performance Test Suite
==============================================
Simulates realistic high-concurrency ticket sale traffic patterns:
1. Catalog Browsing (weight 3)
2. Seat Map Inspection & Availability Summary (weight 4)
3. Virtual Waiting Room Queueing & Polling (weight 4)
4. Seat Hold Claiming under high contention (weight 2)
5. Checkout & Payment Simulation (weight 1)
6. Health & Metrics Observation (weight 1)
"""

import uuid
import random
from locust import HttpUser, task, between, events


class SeatSurgeLoadUser(HttpUser):
    # Think time between 50ms and 300ms to simulate fast flash-sale user behavior
    wait_time = between(0.05, 0.3)

    def on_start(self):
        """Initialize a unique session per simulated user."""
        self.session_id = f"locust_sess_{uuid.uuid4().hex[:12]}"
        self.event_id = 1
        self.admission_token = None
        self.active_hold_id = None
        self.held_seats = []

    @task(3)
    def browse_events(self):
        """Browses event catalog."""
        self.client.get("/api/v1/events", name="GET /api/v1/events")
        self.client.get(f"/api/v1/events/{self.event_id}", name="GET /api/v1/events/:id")

    @task(4)
    def inspect_seat_map(self):
        """
        Inspects seat availability and seat maps (Target: < 200ms p95 latency under load).
        """
        self.client.get(
            f"/api/v1/events/{self.event_id}/seats/summary",
            name="GET /api/v1/events/:id/seats/summary",
        )
        page = random.randint(1, 5)
        self.client.get(
            f"/api/v1/events/{self.event_id}/seats?page={page}&page_size=50",
            name="GET /api/v1/events/:id/seats",
        )

    @task(4)
    def queue_flow(self):
        """Enters virtual waiting room and polls status."""
        headers = {"X-Session-ID": self.session_id}
        res = self.client.post(
            "/api/v1/queue/enter",
            json={"event_id": self.event_id},
            headers=headers,
            name="POST /api/v1/queue/enter",
        )
        if res.status_code == 200:
            data = res.json()
            if data.get("admission_token"):
                self.admission_token = data["admission_token"]

        # Poll status
        self.client.get(
            f"/api/v1/queue/status?event_id={self.event_id}",
            headers=headers,
            name="GET /api/v1/queue/status",
        )

    @task(2)
    def attempt_seat_hold(self):
        """Attempts to hold 1-2 adjacent seats under high contention."""
        seat_id = random.randint(100, 500)
        headers = {
            "X-Session-ID": self.session_id,
            "Idempotency-Key": f"locust_hold_{uuid.uuid4().hex[:8]}",
        }
        if self.admission_token:
            headers["X-Admission-Token"] = self.admission_token

        with self.client.post(
            f"/api/v1/events/{self.event_id}/holds",
            json={"seat_ids": [seat_id]},
            headers=headers,
            name="POST /api/v1/events/:id/holds",
            catch_response=True,
        ) as response:
            if response.status_code == 201:
                # Successfully held seat
                data = response.json()
                self.active_hold_id = data.get("hold_id")
                self.held_seats = data.get("seat_ids", [])
                response.success()
            elif response.status_code in (409, 403):
                # Expected contention or queue restriction under flash sale
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(1)
    def checkout_and_pay(self):
        """Completes checkout if user has an active hold."""
        if not self.active_hold_id:
            return

        headers = {
            "X-Session-ID": self.session_id,
            "Idempotency-Key": f"locust_pay_{uuid.uuid4().hex[:8]}",
        }

        with self.client.post(
            "/api/v1/checkout/pay",
            json={"hold_id": self.active_hold_id, "simulate_failure": False},
            headers=headers,
            name="POST /api/v1/checkout/pay",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                self.active_hold_id = None
                self.held_seats = []
                response.success()
            elif response.status_code in (404, 409):
                # Expired or already resolved
                self.active_hold_id = None
                response.success()
            else:
                response.failure(f"Checkout unexpected failure: {response.status_code}")

    @task(1)
    def check_health(self):
        """Observability health endpoint check."""
        self.client.get("/health", name="GET /health")
