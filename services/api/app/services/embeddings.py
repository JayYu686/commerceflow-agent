from __future__ import annotations

import hashlib
import math
import re
from typing import Any, Protocol

import httpx

from app.core.config import Settings
from app.observability import workflow_span

EMBEDDING_DIMENSION = 1536
EMBEDDING_MODEL = "deterministic-keyword-v2"
DETERMINISTIC_PROVIDER = "deterministic"
OPENAI_COMPATIBLE_PROVIDER = "openai_compatible"

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
        "坏了",
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


class EmbeddingProviderError(ValueError):
    pass


class EmbeddingProvider(Protocol):
    model_name: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


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


class OpenAICompatibleEmbeddingProvider:
    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
        batch_size: int,
        dimensions: int = EMBEDDING_DIMENSION,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model_name = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._batch_size = batch_size
        self._dimensions = dimensions
        self._transport = transport

    def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for offset in range(0, len(texts), self._batch_size):
            embeddings.extend(self._embed_batch(texts[offset : offset + self._batch_size]))
        return embeddings

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        body = {"model": self.model_name, "input": texts}
        try:
            with workflow_span(
                "embedding.request",
                {
                    "embedding.provider": OPENAI_COMPATIBLE_PROVIDER,
                    "embedding.model": self.model_name,
                    "embedding.batch_size": len(texts),
                },
            ):
                with httpx.Client(
                    timeout=self._timeout_seconds,
                    transport=self._transport,
                ) as client:
                    response = client.post(
                        f"{self._base_url}/embeddings",
                        headers={"Authorization": f"Bearer {self._api_key}"},
                        json=body,
                    )
                    response.raise_for_status()
                    payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise EmbeddingProviderError("openai-compatible embedding request failed") from exc
        return validate_embedding_response(payload, len(texts), self._dimensions)


def validate_embedding_response(
    payload: dict[str, Any],
    expected_count: int,
    expected_dimensions: int,
) -> list[list[float]]:
    data = payload.get("data")
    if not isinstance(data, list) or len(data) != expected_count:
        raise EmbeddingProviderError("embedding response count mismatch")
    ordered = sorted(data, key=lambda item: item.get("index", -1))
    embeddings: list[list[float]] = []
    for expected_index, item in enumerate(ordered):
        if not isinstance(item, dict) or item.get("index") != expected_index:
            raise EmbeddingProviderError("embedding response index mismatch")
        vector = item.get("embedding")
        if not isinstance(vector, list) or len(vector) != expected_dimensions:
            raise EmbeddingProviderError("embedding dimension mismatch")
        if not all(
            isinstance(value, int | float) and not isinstance(value, bool) for value in vector
        ):
            raise EmbeddingProviderError("embedding contains a non-numeric value")
        embeddings.append([float(value) for value in vector])
    return embeddings


def create_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider == DETERMINISTIC_PROVIDER:
        return DeterministicEmbeddingProvider()
    if settings.embedding_provider != OPENAI_COMPATIBLE_PROVIDER:
        raise EmbeddingProviderError("unsupported embedding provider")

    api_key = settings.embedding_api_key.get_secret_value()
    if not settings.embedding_model or not settings.embedding_base_url or not api_key:
        raise EmbeddingProviderError("openai-compatible embedding configuration is incomplete")
    if settings.embedding_dimensions != EMBEDDING_DIMENSION:
        raise EmbeddingProviderError("configured embedding dimension must be 1536")
    return OpenAICompatibleEmbeddingProvider(
        model=settings.embedding_model,
        api_key=api_key,
        base_url=settings.embedding_base_url,
        timeout_seconds=settings.embedding_timeout_seconds,
        batch_size=settings.embedding_batch_size,
        dimensions=settings.embedding_dimensions,
    )
