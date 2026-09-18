from datetime import datetime, timedelta
from functools import lru_cache

from sqlalchemy import or_, select

from commerceflow.config import settings
from commerceflow.db import DomainError, digest, utcnow
from commerceflow.models import Policy

REFUND = "quality_issue_refund"
DELAY = "logistics_delay_compensation"


def policy_sources():
    common = {"version": "2", "active": True, "effective_from": "2026-01-01T00:00:00+00:00"}
    return [
        {
            **common,
            "id": "QUALITY-ELECTRONICS-2",
            "intent": REFUND,
            "rules": {"category": "electronics", "aftersales_type": "standard", "hours": 168},
            "content": (
                "标准电子商品签收后7天（168小时，含边界）内首次报告质量问题，"
                "可申请受影响商品行剩余实付金额退款。必须提供清楚的故障描述并由审核员核实证据。"
                "人为损坏、擅自维修或证据不足进入人工处理。退款必须审核通过并由客服确认执行。"
            ),
        },
        {
            **common,
            "id": "LOGISTICS-DELAY-2",
            "intent": DELAY,
            "rules": {"stalled_hours": 72, "coupon_fen": settings().coupon_fen},
            "content": (
                "已支付且未取消的订单须有有效运单及一致的承运轨迹。运输中超过72小时没有移动，"
                "或超过承诺送达时间，符合延误补偿。已签收按实际签收时间判断迟到。"
                "默认补偿10元优惠券，每订单同类延误只补偿一次。超过10元须审核，所有补偿须确认执行。"
            ),
        },
    ]


@lru_cache
def encoder():
    from sentence_transformers import SentenceTransformer

    cfg = settings()
    return SentenceTransformer(
        cfg.embedding_model, revision=cfg.embedding_revision or None, device="cpu"
    )


def embed(texts, query=False):
    if query:
        texts = ["为这个句子生成表示以用于检索相关文章：" + value for value in texts]
    result = encoder().encode(texts, normalize_embeddings=True).tolist()
    if any(len(row) != 512 for row in result):
        raise RuntimeError("Expected actual 512-dimensional BGE embeddings")
    return result


def active_policies(session, intent, now=None):
    now = now or utcnow()
    return list(
        session.scalars(
            select(Policy).where(
                Policy.intent == intent,
                Policy.active.is_(True),
                Policy.effective_from <= now,
                or_(Policy.effective_to.is_(None), Policy.effective_to > now),
            )
        )
    )


def search(session, query, intent):
    vector = embed([query], query=True)[0]
    distance = Policy.embedding.cosine_distance(vector)
    now = utcnow()
    rows = session.execute(
        select(Policy, distance.label("distance"))
        .where(
            Policy.intent == intent,
            Policy.active.is_(True),
            Policy.effective_from <= now,
            or_(Policy.effective_to.is_(None), Policy.effective_to > now),
            Policy.embedding.is_not(None),
        )
        .order_by(distance)
        .limit(5)
    )
    return {
        "hits": [
            {
                "id": p.id,
                "version": p.version,
                "checksum": p.checksum,
                "content": p.content,
                "score": 1 - float(d),
            }
            for p, d in rows
        ]
    }


def moment(value):
    return datetime.fromisoformat(value) if isinstance(value, str) else value


def eligibility(order, history, policy, intent, item_id, defect_quote, reported_at, now=None):
    now = now or utcnow()
    if order["status"] == "cancelled" or order["paid_fen"] <= 0:
        raise DomainError("ineligible_order", "订单未支付或已取消")
    if intent == REFUND:
        item = next((x for x in order["items"] if x["id"] == item_id), None)
        if not item:
            raise DomainError("choose_item", "请明确选择需要售后的商品行")
        if (
            item["category"] != policy.rules["category"]
            or item["aftersales_type"] != policy.rules["aftersales_type"]
        ):
            raise DomainError("manual_review", "此商品不适用标准电子商品质量退款政策")
        delivered = moment(order["delivered_at"])
        if not delivered or not delivered <= reported_at <= delivered + timedelta(
            hours=policy.rules["hours"]
        ):
            raise DomainError("outside_window", "首次报告时间不在签收后7天内")
        if not defect_quote or len(defect_quote.strip()) < 4:
            raise DomainError("missing_evidence", "需要用户对具体故障的清楚描述")
        amount = item["paid_fen"] - item["refunded_fen"]
        entitlement = f"refund:{item_id}"
    elif intent == DELAY:
        events = order["carrier_events"]
        if not order["tracking_no"] or not events:
            raise DomainError("missing_tracking", "缺少有效运单或承运轨迹")
        dates = [moment(e["at"]) for e in events]
        if dates != sorted(dates) or any(d > now or d < moment(order["paid_at"]) for d in dates):
            raise DomainError("inconsistent_tracking", "物流轨迹时间不一致，需人工处理")
        delivered = moment(order["delivered_at"])
        if delivered and (delivered > now or delivered < dates[-1]):
            raise DomainError("inconsistent_tracking", "签收与轨迹时间不一致")
        movements = [moment(e["at"]) for e in events if e["kind"] in {"picked_up", "movement"}]
        stalled = (
            not delivered
            and movements
            and now - max(movements) > timedelta(hours=policy.rules["stalled_hours"])
        )
        late = (delivered or now) > moment(order["promised_at"])
        if not stalled and not late:
            raise DomainError("not_delayed", "真实轨迹未达到延误补偿条件")
        amount = policy.rules["coupon_fen"]
        entitlement = f"delay:{order['order_no']}"
        item_id = None
    else:
        raise DomainError("unsupported_intent", "仅支持质量退款和物流延误补偿")
    if amount <= 0 or any(x["entitlement_key"] == entitlement for x in history["results"]):
        raise DomainError("already_processed", "该售后权益已经处理，不能重复申请")
    return {
        "intent": intent,
        "order_no": order["order_no"],
        "item_id": item_id,
        "amount_fen": amount,
        "currency": "CNY",
        "entitlement_key": entitlement,
        "policy_id": policy.id,
        "policy_checksum": policy.checksum,
        "defect_quote": defect_quote if intent == REFUND else "",
        "reported_at": reported_at.isoformat(),
        "requires_approval": intent == REFUND or amount > settings().approval_threshold_fen,
    }


def assert_policy(session, payload):
    policies = active_policies(session, payload["intent"])
    if len(policies) != 1:
        raise DomainError("policy_conflict", "政策缺失或存在冲突，不能执行")
    policy = policies[0]
    if policy.id != payload["policy_id"] or policy.checksum != payload["policy_checksum"]:
        raise DomainError("policy_changed", "政策版本已改变，需要重新调查并授权")
    if policy.checksum != digest(
        {"content": policy.content, "rules": policy.rules, "version": policy.version}
    ):
        raise DomainError("policy_corrupt", "政策内容与发布版本不一致")
    return policy
