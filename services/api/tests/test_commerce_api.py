from fastapi.testclient import TestClient

from scripts.seed_demo_data import FIXED_DELAYED_ORDER_NO, FIXED_QUALITY_ORDER_NO


def test_read_order_returns_order_snapshot(client: TestClient) -> None:
    response = client.get(f"/api/orders/{FIXED_QUALITY_ORDER_NO}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["order_no"] == FIXED_QUALITY_ORDER_NO
    assert payload["status"] == "delivered"
    assert payload["aftersales_status"] == "none"
    assert payload["paid_amount"] == "299.00"
    assert payload["customer"]["id"] == 23
    assert payload["items"][0]["unit_price"] == "299.00"
    assert payload["items"][0]["line_amount"] == "299.00"
    assert payload["items"][0]["product"]["sku"] == "ELEC-HEADPHONE-001"


def test_read_order_returns_uniform_not_found(client: TestClient) -> None:
    response = client.get("/api/orders/UNKNOWN")

    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "code": "not_found",
            "resource": "order",
            "identifier": "UNKNOWN",
            "message": "order not found",
        }
    }


def test_read_logistics_returns_ordered_events(client: TestClient) -> None:
    response = client.get(f"/api/orders/{FIXED_DELAYED_ORDER_NO}/logistics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["order_no"] == FIXED_DELAYED_ORDER_NO
    assert payload["carrier"] == "SF Express"
    assert payload["tracking_no"] == "TRK202605000071"
    assert payload["status"] == "delayed"
    assert payload["delivered_at"] is None
    sequences = [event["sequence"] for event in payload["events"]]
    assert sequences == sorted(sequences)
    assert sequences == [1, 2, 3, 4]


def test_read_logistics_returns_uniform_not_found(client: TestClient) -> None:
    response = client.get("/api/orders/UNKNOWN/logistics")

    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "code": "not_found",
            "resource": "logistics",
            "identifier": "UNKNOWN",
            "message": "logistics not found",
        }
    }
