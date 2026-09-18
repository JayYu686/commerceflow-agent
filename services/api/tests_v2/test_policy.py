from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from commerceflow.db import DomainError
from commerceflow.policy import DELAY, REFUND, eligibility, policy_sources

NOW = datetime(2026, 9, 17, 12, tzinfo=UTC)


def facts():
    return {
        "order_no": "TEST",
        "status": "delivered",
        "paid_fen": 24900,
        "paid_at": NOW - timedelta(days=15),
        "delivered_at": NOW - timedelta(days=2),
        "promised_at": NOW - timedelta(days=3),
        "tracking_no": "TRACK",
        "carrier_events": [{"kind": "movement", "at": (NOW - timedelta(days=4)).isoformat()}],
        "items": [
            {
                "id": "ITEM1",
                "category": "electronics",
                "aftersales_type": "standard",
                "paid_fen": 19900,
                "refunded_fen": 0,
            }
        ],
    }


def check(order=None, intent=REFUND, reported=NOW, history=None, quote="耳机左耳没有声音"):
    source = next(s for s in policy_sources() if s["intent"] == intent)
    source["checksum"] = "test"
    return eligibility(
        order or facts(),
        history or {"results": []},
        SimpleNamespace(**source),
        intent,
        "ITEM1",
        quote,
        reported,
        now=NOW,
    )


def test_refund_only_affected_item_remaining_payment():
    order = facts()
    order["items"][0]["refunded_fen"] = 900
    assert check(order)["amount_fen"] == 19000
    assert check(order)["requires_approval"]


@pytest.mark.parametrize("hours,eligible", [(0, True), (168, True), (168.001, False), (-1, False)])
def test_refund_window_boundaries(hours, eligible):
    order = facts()
    reported = order["delivered_at"] + timedelta(hours=hours)
    if eligible:
        assert check(order, reported=reported)["amount_fen"] == 19900
    else:
        with pytest.raises(DomainError, match="7天"):
            check(order, reported=reported)


@pytest.mark.parametrize(
    "change", ["cancelled", "no_payment", "category", "special", "refunded", "no_delivery"]
)
def test_refund_ineligible_facts(change):
    order = facts()
    if change == "cancelled":
        order["status"] = "cancelled"
    if change == "no_payment":
        order["paid_fen"] = 0
    if change == "category":
        order["items"][0]["category"] = "fresh"
    if change == "special":
        order["items"][0]["aftersales_type"] = "special"
    if change == "refunded":
        order["items"][0]["refunded_fen"] = 19900
    if change == "no_delivery":
        order["delivered_at"] = None
    with pytest.raises(DomainError):
        check(order)


def test_missing_defect_cannot_propose():
    with pytest.raises(DomainError):
        check(quote="")


def test_duplicate_entitlement_is_not_amount_or_policy_dependent():
    with pytest.raises(DomainError):
        check(history={"results": [{"entitlement_key": "refund:ITEM1", "amount_fen": 1}]})


@pytest.mark.parametrize("hours,eligible", [(72, False), (72.01, True)])
def test_stall_boundary(hours, eligible):
    order = facts()
    order["delivered_at"] = None
    order["promised_at"] = NOW + timedelta(days=1)
    order["carrier_events"][0]["at"] = (NOW - timedelta(hours=hours)).isoformat()
    if eligible:
        result = check(order, DELAY)
        assert result["amount_fen"] == 1000 and not result["requires_approval"]
    else:
        with pytest.raises(DomainError):
            check(order, DELAY)


def test_delivered_on_time_does_not_become_delayed_as_time_passes():
    order = facts()
    order["promised_at"] = NOW - timedelta(days=1)
    with pytest.raises(DomainError):
        check(order, DELAY)


def test_actual_late_delivery_qualifies():
    assert check(facts(), DELAY)["amount_fen"] == 1000


def test_movement_after_signed_delivery_is_inconsistent():
    order = facts()
    order["carrier_events"].append(
        {"kind": "movement", "at": (NOW - timedelta(days=1)).isoformat()}
    )
    with pytest.raises(DomainError, match="签收与轨迹"):
        check(order, DELAY)


@pytest.mark.parametrize("amount,requires_review", [(1000, False), (1001, True)])
def test_coupon_review_threshold(amount, requires_review):
    source = next(s for s in policy_sources() if s["intent"] == DELAY)
    source["rules"]["coupon_fen"] = amount
    source["checksum"] = "test"
    result = eligibility(
        facts(), {"results": []}, SimpleNamespace(**source), DELAY, None, "", NOW, now=NOW
    )
    assert result["requires_approval"] is requires_review


@pytest.mark.parametrize(
    "events", [[], [{"kind": "movement", "at": (NOW + timedelta(days=1)).isoformat()}]]
)
def test_no_or_inconsistent_tracking_is_blocked(events):
    order = facts()
    order["carrier_events"] = events
    with pytest.raises(DomainError):
        check(order, DELAY)
