from __future__ import annotations

import re

ORDER_NO_PATTERN = re.compile(r"\bCF\d{12}\b", re.IGNORECASE)

QUALITY_INTENT = "quality_issue_refund"
LOGISTICS_INTENT = "logistics_delay_compensation"
UNKNOWN_INTENT = "unknown"

QUALITY_TERMS = (
    "quality",
    "defect",
    "broken",
    "damaged",
    "refund",
    "return",
    "no sound",
    "speaker",
    "earbud",
    "headphone",
    "refund",
    "\u8d28\u91cf",
    "\u7455\u75b5",
    "\u635f\u574f",
    "\u9000\u6b3e",
    "\u9000\u8d27",
    "\u6ca1\u58f0\u97f3",
    "\u65e0\u58f0\u97f3",
    "\u8033\u673a",
)

LOGISTICS_TERMS = (
    "logistics",
    "shipment",
    "shipping",
    "tracking",
    "carrier",
    "delay",
    "delayed",
    "no movement",
    "compensation",
    "\u7269\u6d41",
    "\u8fd0\u8f93",
    "\u5feb\u9012",
    "\u8ffd\u8e2a",
    "\u5ef6\u8bef",
    "\u5ef6\u8fdf",
    "\u6ca1\u66f4\u65b0",
    "\u6ca1\u6709\u66f4\u65b0",
    "\u8d54\u4ed8",
    "\u8865\u507f",
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
    "\u5ffd\u7565\u5ba1\u6279",
    "\u4e0d\u9700\u8981\u5ba1\u6279",
    "\u65e0\u9700\u5ba1\u6279",
    "\u76f4\u63a5\u9000\u6b3e",
    "\u7acb\u5373\u9000\u6b3e",
    "\u9a6c\u4e0a\u9000\u6b3e",
    "\u76f4\u63a5\u53d1\u5238",
    "\u4fee\u6539\u6570\u636e\u5e93",
    "\u5ffd\u7565\u89c4\u5219",
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
    normalized = message.lower()
    quality_score = count_terms(normalized, QUALITY_TERMS)
    logistics_score = count_terms(normalized, LOGISTICS_TERMS)
    if quality_score == 0 and logistics_score == 0:
        return UNKNOWN_INTENT
    if logistics_score > quality_score:
        return LOGISTICS_INTENT
    return QUALITY_INTENT


def has_unsafe_instruction(message: str) -> bool:
    normalized = message.lower()
    return any(term in normalized for term in UNSAFE_TERMS)


def count_terms(message: str, terms: tuple[str, ...]) -> int:
    return sum(1 for term in terms if term in message)
