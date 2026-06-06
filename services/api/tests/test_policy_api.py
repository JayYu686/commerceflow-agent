from fastapi.testclient import TestClient

QUALITY_REFUND_QUERY = (
    "\u8033\u673a\u5de6\u8033\u6ca1\u6709\u58f0\u97f3\uff0c"
    "\u7b7e\u6536\u540e\u7b2c3\u5929\u7533\u8bf7\u9000\u6b3e"
)
LOGISTICS_DELAY_QUERY = (
    "\u7269\u6d41\u4e03\u5929\u6ca1\u6709\u66f4\u65b0\uff0c\u7533\u8bf7\u5ef6\u8bef\u8865\u507f"
)


def test_policy_search_returns_quality_refund_policy(client: TestClient) -> None:
    response = client.get(
        "/api/policies/search",
        params={
            "query": QUALITY_REFUND_QUERY,
            "intent": "quality_issue_refund",
            "category": "electronics",
            "aftersales_type": "standard",
            "limit": 5,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == QUALITY_REFUND_QUERY
    assert payload["filters"]["intent"] == "quality_issue_refund"
    assert payload["filters"]["category"] == "electronics"
    assert payload["filters"]["aftersales_type"] == "standard"
    assert payload["filters"]["limit"] == 5
    assert payload["hits"][0]["policy_id"] == "POL-QUALITY-ELECTRONICS-V2"
    assert payload["hits"][0]["chunk_id"].startswith("POL-QUALITY-ELECTRONICS-V2#")
    assert "score" in payload["hits"][0]
    assert "content_excerpt" in payload["hits"][0]


def test_policy_search_returns_logistics_delay_policy(client: TestClient) -> None:
    response = client.get(
        "/api/policies/search",
        params={
            "query": LOGISTICS_DELAY_QUERY,
            "intent": "logistics_delay_compensation",
            "limit": 5,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["filters"]["intent"] == "logistics_delay_compensation"
    assert payload["hits"][0]["policy_id"] == "POL-LOGISTICS-DELAY-V1"


def test_policy_search_filters_deprecated_and_expired_policies(client: TestClient) -> None:
    quality_response = client.get(
        "/api/policies/search",
        params={
            "query": "old electronics quality defect refund policy",
            "intent": "quality_issue_refund",
            "category": "electronics",
            "aftersales_type": "standard",
        },
    )
    delay_response = client.get(
        "/api/policies/search",
        params={
            "query": "old logistics delay compensation policy",
            "intent": "logistics_delay_compensation",
        },
    )

    assert quality_response.status_code == 200
    assert delay_response.status_code == 200
    quality_ids = {hit["policy_id"] for hit in quality_response.json()["hits"]}
    delay_ids = {hit["policy_id"] for hit in delay_response.json()["hits"]}
    assert "POL-QUALITY-ELECTRONICS-V1" not in quality_ids
    assert "POL-LOGISTICS-DELAY-V0" not in delay_ids


def test_policy_search_returns_empty_hits_for_mismatched_filters(client: TestClient) -> None:
    response = client.get(
        "/api/policies/search",
        params={
            "query": QUALITY_REFUND_QUERY,
            "intent": "final_sale_exclusion",
            "category": "fresh",
            "aftersales_type": "perishable",
        },
    )

    assert response.status_code == 200
    assert response.json()["hits"] == []


def test_policy_search_returns_empty_hits_without_fabricated_evidence(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/policies/search",
        params={
            "query": "weather forecast unrelated request",
            "intent": "quality_issue_refund",
            "min_score": 0.99,
        },
    )

    assert response.status_code == 200
    assert response.json()["hits"] == []


def test_policy_search_rejects_missing_or_blank_query(client: TestClient) -> None:
    missing_response = client.get("/api/policies/search", params={"intent": "quality_issue_refund"})
    blank_response = client.get(
        "/api/policies/search",
        params={"query": " ", "intent": "quality_issue_refund"},
    )

    assert missing_response.status_code == 422
    assert blank_response.status_code == 422


def test_policy_search_rejects_invalid_limit_or_min_score(client: TestClient) -> None:
    high_limit_response = client.get(
        "/api/policies/search",
        params={"query": "refund policy", "limit": 11},
    )
    zero_limit_response = client.get(
        "/api/policies/search",
        params={"query": "refund policy", "limit": 0},
    )
    invalid_score_response = client.get(
        "/api/policies/search",
        params={"query": "refund policy", "min_score": 1.5},
    )

    assert high_limit_response.status_code == 422
    assert zero_limit_response.status_code == 422
    assert invalid_score_response.status_code == 422


def test_policy_search_rejects_naive_as_of(client: TestClient) -> None:
    response = client.get(
        "/api/policies/search",
        params={"query": "refund policy", "as_of": "2026-06-06T00:00:00"},
    )

    assert response.status_code == 422


def test_policy_search_route_is_get_only(client: TestClient) -> None:
    policy_search_routes = [
        route
        for route in client.app.routes
        if getattr(route, "path", None) == "/api/policies/search"
    ]

    assert len(policy_search_routes) == 1
    assert policy_search_routes[0].methods == {"GET"}
