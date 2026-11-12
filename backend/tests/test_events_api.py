import pytest


def test_list_events(client):
    response = client.get("/api/v1/events")
    assert response.status_code == 200
    data = response.json()
    assert "events" in data
    assert data["count"] >= 1
    assert data["events"][0]["id"] == 1
    assert data["events"][0]["name"] == "YUKTIK 2026 Grand Concert"
    assert data["events"][0]["total_seats"] == 5040


def test_get_event_by_id(client):
    response = client.get("/api/v1/events/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "YUKTIK 2026 Grand Concert"
    assert data["venue_name"] == "YUKTIK Grand Auditorium"


def test_get_nonexistent_event_structured_error(client):
    """Verifies that 404 errors return the agreed RFC 7807-inspired error envelope."""
    response = client.get("/api/v1/events/9999")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data, "Error response must contain top-level 'error' key"
    err = data["error"]
    assert err["code"] == "NOT_FOUND"
    assert "not found" in err["message"].lower()
    assert "timestamp" in err


def test_validation_error_structured_envelope(client):
    """Verifies that 422 validation errors return the structured error envelope."""
    # Pass an invalid page_size (e.g. string or negative number)
    response = client.get("/api/v1/events/1/seats?page=-5")
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    err = data["error"]
    assert err["code"] == "VALIDATION_ERROR"
    assert "details" in err
    assert "errors" in err["details"]


def test_get_event_seats_pagination(client):
    response = client.get("/api/v1/events/1/seats?page=1&page_size=50")
    assert response.status_code == 200
    data = response.json()
    assert data["event_id"] == 1
    assert data["total_seats"] == 5040
    assert len(data["seats"]) == 50
    assert data["page"] == 1
    assert data["page_size"] == 50
    assert data["total_pages"] == 101  # ceil(5040 / 50)
    # Verify standard seat identifier is seat_id (docs/api-contract.md §4)
    assert "seat_id" in data["seats"][0]
    assert data["seats"][0]["seat_id"] == 1


def test_get_event_seats_filter_tier(client):
    response = client.get("/api/v1/events/1/seats?tier=VIP&page_size=300")
    assert response.status_code == 200
    data = response.json()
    assert data["total_seats"] == 240
    assert len(data["seats"]) == 240
    assert all(s["tier"] == "VIP" for s in data["seats"])


def test_get_event_seats_filter_row(client):
    response = client.get("/api/v1/events/1/seats?row=A")
    assert response.status_code == 200
    data = response.json()
    assert data["total_seats"] == 60
    assert len(data["seats"]) == 60
    assert all(s["row"] == "A" for s in data["seats"])


def test_get_single_seat(client):
    """Verifies single seat retrieval uses standardized seat_id key."""
    response = client.get("/api/v1/events/1/seats/1")
    assert response.status_code == 200
    data = response.json()
    assert data["seat_id"] == 1
    assert data["row"] == "A"
    assert data["number"] == 1
    assert data["tier"] == "VIP"
    assert data["status"] in ["AVAILABLE", "HELD", "PAYING", "SOLD"]


def test_get_seat_availability_summary(client):
    response = client.get("/api/v1/events/1/availability")
    assert response.status_code == 200
    data = response.json()
    assert data["event_id"] == 1
    assert data["total_seats"] == 5040
    assert "tiers" in data
    assert "VIP" in data["tiers"]
    assert "PREMIUM" in data["tiers"]
    assert "STANDARD" in data["tiers"]
    assert data["tiers"]["VIP"]["total"] == 240
    assert data["tiers"]["PREMIUM"]["total"] == 1200
    assert data["tiers"]["STANDARD"]["total"] == 3600
