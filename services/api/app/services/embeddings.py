import hashlib
import math
import re
from typing import Protocol

EMBEDDING_DIMENSION = 1536
EMBEDDING_MODEL = "deterministic-keyword-v1"

TOKEN_PATTERN = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]+")

KEYWORD_ALIASES = {
    "quality": [
        "quality",
        "defect",
        "defects",
        "fault",
        "faulty",
        "broken",
        "malfunction",
        "瑕疵",
        "质量",
        "故障",
        "坏",
    ],
    "electronics": [
        "electronics",
        "electronic",
        "headphone",
        "headphones",
        "earbud",
        "earbuds",
        "耳机",
    ],
    "audio": [
        "audio",
        "sound",
        "speaker",
        "left ear",
        "right ear",
        "no sound",
        "无声",
        "没声音",
    ],
    "refund": ["refund", "return", "refundable", "退货", "退款", "退"],
    "evidence": ["evidence", "proof", "photo", "video", "证明", "凭证", "照片", "视频"],
    "approval": ["approval", "human approval", "manual approval", "审批", "人工"],
    "logistics": [
        "logistics",
        "shipment",
        "delivery",
        "carrier",
        "tracking",
        "物流",
        "快递",
        "运单",
    ],
    "delay": [
        "delay",
        "delayed",
        "late",
        "no movement",
        "overdue",
        "延误",
        "延迟",
        "没有更新",
    ],
    "compensation": ["compensation", "coupon", "credit", "赔付", "补偿", "优惠券"],
    "fresh": ["fresh", "perishable", "spoilage", "spoiled", "生鲜", "腐坏", "变质"],
    "apparel": ["apparel", "size", "exchange", "clothing", "服饰", "尺码", "换货"],
    "appliance": ["appliance", "warranty", "repair", "replacement", "家电", "保修", "维修"],
    "home": ["home", "damaged", "package", "家具", "家居", "破损", "损坏"],
    "final_sale": ["final sale", "no return", "特价", "清仓", "不可退"],
    "expired": ["expired", "deprecated", "old", "过期", "失效", "废弃"],
}


class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        pass


class DeterministicEmbeddingProvider:
    model_name = EMBEDDING_MODEL

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        normalized = text.lower()
        vector = [0.0] * EMBEDDING_DIMENSION

        for token in TOKEN_PATTERN.findall(normalized):
            self._add_token(vector, token, 1.0)

        for canonical, aliases in KEYWORD_ALIASES.items():
            for alias in aliases:
                if alias in normalized:
                    self._add_token(vector, canonical, 4.0)
                    break

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]

    @staticmethod
    def _add_token(vector: list[float], token: str, weight: float) -> None:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSION
        vector[index] += weight
