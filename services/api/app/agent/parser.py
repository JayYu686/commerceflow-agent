from __future__ import annotations

import re

ORDER_NO_PATTERN = re.compile(r"\bCF\d{12}\b", re.IGNORECASE)

QUALITY_INTENT = "quality_issue_refund"
LOGISTICS_INTENT = "logistics_delay_compensation"
UNKNOWN_INTENT = "unknown"

REFUND_ACTION_TERMS = (
    "refund",
    "return",
    "money back",
    "退货",
    "退款",
    "退钱",
    "退回",
)

QUALITY_CONTEXT_TERMS = (
    "quality",
    "defect",
    "defective",
    "broken",
    "break",
    "damaged",
    "damage",
    "spoiled",
    "no sound",
    "no audio",
    "not working",
    "does not work",
    "cannot use",
    "unusable",
    "speaker",
    "earbud",
    "earbuds",
    "headphone",
    "headphones",
    "质量",
    "质量问题",
    "瑕疵",
    "损坏",
    "坏了",
    "破损",
    "故障",
    "无法使用",
    "不能用",
    "没法用",
    "没有声音",
    "没声音",
    "无声音",
    "无声",
    "左耳没声音",
    "左耳没有声音",
    "耳机",
    "商品坏了",
    "商品有问题",
    "有质量问题",
)

COMPENSATION_ACTION_TERMS = (
    "compensation",
    "compensate",
    "coupon",
    "赔付",
    "补偿",
    "赔偿",
)

LOGISTICS_CONTEXT_TERMS = (
    "logistics",
    "shipment",
    "shipping",
    "delivery",
    "tracking",
    "carrier",
    "delay",
    "delayed",
    "no movement",
    "not received",
    "物流",
    "运输",
    "快递",
    "包裹",
    "追踪",
    "延误",
    "延迟",
    "没更新",
    "没有更新",
    "七天没更新",
    "一直没更新",
    "一直没收到",
    "没收到",
    "没有收到",
)

UNSAFE_TERMS = (
    "bypass approval",
    "skip approval",
    "ignore approval",
    "without approval",
    "no approval",
    "direct refund",
    "execute refund",
    "refund immediately",
    "issue coupon now",
    "modify database",
    "ignore all rules",
    "\u7ed5\u8fc7\u5ba1\u6279",
    "\u8df3\u8fc7\u5ba1\u6279",
    "\u8df3\u8fc7\u5ba1\u6838",
    "\u5ffd\u7565\u5ba1\u6279",
    "\u4e0d\u9700\u8981\u5ba1\u6279",
    "\u65e0\u9700\u5ba1\u6279",
    "\u4e0d\u8981\u5ba1\u6838",
    "\u4e0d\u7528\u5ba1\u6838",
    "\u4e0d\u5ba1\u6838",
    "\u76f4\u63a5\u9000\u6b3e",
    "\u7acb\u5373\u9000\u6b3e",
    "\u9a6c\u4e0a\u9000\u6b3e",
    "\u76f4\u63a5\u53d1\u5238",
    "\u4fee\u6539\u6570\u636e\u5e93",
    "\u5ffd\u7565\u89c4\u5219",
    "\u7ed5\u8fc7\u89c4\u5219",
)


def extract_order_numbers(message: str) -> list[str]:
    seen: set[str] = set()
    order_numbers: list[str] = []
    for match in ORDER_NO_PATTERN.finditer(message):
        order_no = match.group(0).upper()
        if order_no not in seen:
            seen.add(order_no)
            order_numbers.append(order_no)
    return order_numbers


def classify_intent(message: str) -> str:
    normalized = normalize_message(message)
    wants_refund = has_any_term(normalized, REFUND_ACTION_TERMS)
    has_quality_context = has_any_term(normalized, QUALITY_CONTEXT_TERMS)
    wants_compensation = has_any_term(normalized, COMPENSATION_ACTION_TERMS)
    has_logistics_context = has_any_term(normalized, LOGISTICS_CONTEXT_TERMS)

    if has_logistics_context and wants_compensation:
        return LOGISTICS_INTENT
    if has_quality_context and wants_refund:
        return QUALITY_INTENT
    return UNKNOWN_INTENT


def has_unsafe_instruction(message: str) -> bool:
    normalized = normalize_message(message)
    return any(term in normalized for term in UNSAFE_TERMS)


def has_any_term(message: str, terms: tuple[str, ...]) -> bool:
    return any(term in message for term in terms)


def normalize_message(message: str) -> str:
    return re.sub(r"\s+", " ", message.lower()).strip()
