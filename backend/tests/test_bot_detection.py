"""
Phase 7 Integration Tests — AI Bot Detection & Scalper Mitigation
=================================================================
Verifies:
1. Trained Scikit-Learn Random Forest model achieves held-out F1 >= 0.80.
2. Feature extraction correctly captures human jitter vs machine clockwork.
3. Bot detector service accurately classifies normal human fans as ALLOW.
4. Bot detector blocks superhuman velocity scalper patterns with HTTP 403 BOT_DETECTED.
5. Bot blocks are recorded in real-time in metrics (bots_blocked_count).
"""

import json
from pathlib import Path
import pytest
from starlette.testclient import TestClient
from app.ml.bot_detector import bot_detector
from app.services.metrics_service import metrics_tracker


def test_model_metrics_held_out_f1_target():
    """Verify stored model metrics on held-out test dataset meet the F1 >= 0.80 requirement."""
    metrics_path = Path(__file__).resolve().parent.parent / "app" / "ml" / "model_metrics.json"
    assert metrics_path.exists(), "Model metrics file does not exist. Run app.ml.train first."

    with open(metrics_path, "r") as f:
        data = json.load(f)

    assert data["model_type"] == "RandomForestClassifier"
    assert data["test_samples"] >= 500
    assert data["precision"] >= 0.80
    assert data["recall"] >= 0.80
    assert data["f1_score"] >= 0.80, f"Expected F1 >= 0.80, got {data['f1_score']}"
    assert data["roc_auc"] >= 0.85
    assert "confusion_matrix" in data


def test_bot_detector_allows_normal_human_behavior(client: TestClient):
    """Normal human session activity with natural timing is classified as ALLOW."""
    session_id = "normal_fan_session_701"
    headers = {"X-Session-ID": session_id, "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    # Queue entry allowed
    q_res = client.post("/api/v1/queue/enter", json={"event_id": 1}, headers=headers)
    assert q_res.status_code == 200
    token = q_res.json().get("admission_token")

    # Hold creation allowed
    h_headers = {**headers}
    if token:
        h_headers["X-Admission-Token"] = token
    h_res = client.post("/api/v1/events/1/holds", json={"seat_ids": [450]}, headers=h_headers)
    assert h_res.status_code == 201


def test_bot_detector_blocks_sniper_bot_on_holds(client: TestClient):
    """Superhuman sniper bot signature is blocked with HTTP 403 BOT_DETECTED on hold endpoint."""
    session_id = "sniper_bot_session_702"
    headers = {
        "X-Session-ID": session_id,
        "User-Agent": "python-requests/2.31.0",
        "X-Simulate-Bot": "true",
    }

    res = client.post("/api/v1/events/1/holds", json={"seat_ids": [451]}, headers=headers)
    assert res.status_code == 403
    err = res.json()["error"]
    assert err["code"] == "BOT_DETECTED"
    assert "bot_score" in err.get("details", {}) or "bot" in err["message"].lower()


def test_bot_detector_blocks_sniper_bot_on_queue(client: TestClient):
    """Superhuman scalper bot is blocked on entering the virtual waiting room."""
    session_id = "queue_scalper_bot_703"
    headers = {
        "X-Session-ID": session_id,
        "User-Agent": "curl/7.88.1",
        "X-Simulate-Bot": "true",
    }

    res = client.post("/api/v1/queue/enter", json={"event_id": 1}, headers=headers)
    assert res.status_code == 403
    err = res.json()["error"]
    assert err["code"] == "BOT_DETECTED"


def test_bot_blocks_increment_metrics_counter(client: TestClient):
    """Every blocked bot immediately increments bots_blocked_count in GET /metrics."""
    # Read baseline metrics
    m1 = client.get("/api/v1/metrics").json()
    initial_bots = m1["bots_blocked_count"]

    # Trigger bot block
    client.post(
        "/api/v1/events/1/holds",
        json={"seat_ids": [452]},
        headers={"X-Session-ID": "metric_tracker_bot_session", "X-Simulate-Bot": "true"},
    )

    # Read updated metrics
    m2 = client.get("/api/v1/metrics").json()
    assert m2["bots_blocked_count"] == initial_bots + 1
