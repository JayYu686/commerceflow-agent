from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.agent.parser import (
    LOGISTICS_INTENT,
    ORDER_NO_PATTERN,
    QUALITY_INTENT,
    UNKNOWN_INTENT,
    classify_intent,
    extract_order_numbers,
    has_unsafe_instruction,
)
from app.core.config import Settings

INTENT_TASK = "intent_extraction"
CUSTOMER_REPLY_TASK = "customer_reply"
FAKE_LLM_PROVIDER = "fake"
DISABLED_LLM_PROVIDER = "disabled"
OPENAI_COMPATIBLE_LLM_PROVIDER = "openai_compatible"

VALID_LLM_INTENTS = {QUALITY_INTENT, LOGISTICS_INTENT, UNKNOWN_INTENT}
MIN_LLM_INTENT_CONFIDENCE = 0.75

FORBIDDEN_REPLY_CLAIMS = (
    "已退款",
    "已赔付",
    "已发放优惠券",
    "已创建工单",
    "已自动处理完成",
    "可以绕过审批",
    "无需审批即可",
    "refund has been executed",
    "coupon has been issued",
    "ticket has been created",
    "approval can be skipped",
)


class LLMOutputError(ValueError):
    pass


class LLMIntentCandidate(BaseModel):
    intent: str
    order_numbers: list[str] = Field(default_factory=list)
    unsafe_request: bool = False
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1)

    @field_validator("intent")
    @classmethod
    def validate_intent(cls, value: str) -> str:
        if value not in VALID_LLM_INTENTS:
            raise ValueError("unsupported intent")
        return value

    @field_validator("order_numbers")
    @classmethod
    def validate_order_numbers(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            order_no = value.upper()
            if ORDER_NO_PATTERN.fullmatch(order_no) is None:
                raise ValueError("invalid order number")
            if order_no not in normalized:
                normalized.append(order_no)
        return normalized


class LLMCustomerReplyDraft(BaseModel):
    reply: str = Field(min_length=1)
    cited_policy_ids: list[str] = Field(default_factory=list)
    cited_fact_fields: list[str] = Field(default_factory=list)

    @field_validator("reply")
    @classmethod
    def reject_forbidden_claims(cls, value: str) -> str:
        normalized = value.lower()
        if any(claim in normalized for claim in FORBIDDEN_REPLY_CLAIMS):
            raise ValueError("reply claims an unsupported business action")
        return value


@dataclass(frozen=True)
class LLMResult:
    provider: str
    model: str | None
    raw_text: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    estimated_cost: str | None = None
    latency_ms: int | None = None


class LLMProvider(Protocol):
    provider: str
    model: str | None

    def generate_structured(
        self,
        *,
        task: str,
        prompt: str,
        schema_name: str,
    ) -> LLMResult: ...


class FakeLLMProvider:
    provider = FAKE_LLM_PROVIDER

    def __init__(
        self,
        *,
        model: str = "fake-after-sales-v1",
        responses: dict[str, str | Exception] | None = None,
    ) -> None:
        self.model = model
        self.responses = responses or {}

    def generate_structured(
        self,
        *,
        task: str,
        prompt: str,
        schema_name: str,
    ) -> LLMResult:
        configured_response = self.responses.get(task)
        if isinstance(configured_response, Exception):
            raise configured_response
        if isinstance(configured_response, str):
            raw_text = configured_response
        elif task == INTENT_TASK:
            raw_text = self._intent_response(prompt)
        elif task == CUSTOMER_REPLY_TASK:
            raw_text = self._customer_reply_response(prompt)
        else:
            raise LLMOutputError(f"Unsupported fake LLM task: {task}")

        return LLMResult(
            provider=self.provider,
            model=self.model,
            raw_text=raw_text,
            prompt_tokens=estimate_tokens(prompt),
            completion_tokens=estimate_tokens(raw_text),
            estimated_cost=None,
            latency_ms=0,
        )

    def _intent_response(self, prompt: str) -> str:
        payload = json.loads(prompt)
        message = payload["message"]
        candidate = {
            "intent": classify_intent(message),
            "order_numbers": extract_order_numbers(message),
            "unsafe_request": has_unsafe_instruction(message),
            "confidence": 0.92,
            "reason": "Deterministic fake provider mirrors supported after-sales patterns.",
        }
        return json.dumps(candidate, ensure_ascii=False)

    def _customer_reply_response(self, prompt: str) -> str:
        payload = json.loads(prompt)
        context = payload["context"]
        policy_ids = context["allowed_policy_ids"]
        fact_fields = context["allowed_fact_fields"]
        recommendation = context["recommendation"]
        risk = context["risk"]
        error_codes = set(context["error_codes"])

        if "missing_order_no" in error_codes:
            reply = "当前还缺少订单号，请先提供一个订单号；系统只会生成处理建议预览。"
            cited_policy_ids: list[str] = []
            cited_fact_fields: list[str] = []
        elif "order_not_found" in error_codes:
            reply = (
                "当前没有查到该订单的业务事实，请先核对订单号；系统不会执行退款、赔付或工单操作。"
            )
            cited_policy_ids = []
            cited_fact_fields = []
        elif not policy_ids:
            reply = "当前没有找到有效的售后政策依据，建议转人工核查；系统不会生成执行承诺。"
            cited_policy_ids = []
            cited_fact_fields = fact_fields[:2]
        elif recommendation.get("action_type") == "refund_review":
            reply = (
                "已根据订单事实和售后政策生成质量问题退款审核预览；"
                "当前不会直接执行退款，后续仍需按规则进行人工审批。"
            )
            cited_policy_ids = policy_ids[:1]
            cited_fact_fields = fact_fields[:3]
        elif recommendation.get("action_type") == "delay_compensation_review":
            reply = (
                "已根据物流事实和售后政策生成延误补偿审核预览；"
                "当前不会直接发放优惠券或修改业务状态。"
            )
            cited_policy_ids = policy_ids[:1]
            cited_fact_fields = fact_fields[:3]
        elif risk.get("level") == "critical":
            reply = "当前请求包含绕过审批或直接执行业务动作的内容，系统已阻止继续生成执行建议。"
            cited_policy_ids = []
            cited_fact_fields = []
        else:
            reply = "当前仅生成售后处理建议预览，不会直接执行退款、赔付、发券或工单操作。"
            cited_policy_ids = policy_ids[:1]
            cited_fact_fields = fact_fields[:2]

        return json.dumps(
            {
                "reply": reply,
                "cited_policy_ids": cited_policy_ids,
                "cited_fact_fields": cited_fact_fields,
            },
            ensure_ascii=False,
        )


class OpenAICompatibleLLMProvider:
    provider = OPENAI_COMPATIBLE_LLM_PROVIDER

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
        max_tokens: int,
        temperature: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._transport = transport

    def generate_structured(
        self,
        *,
        task: str,
        prompt: str,
        schema_name: str,
    ) -> LLMResult:
        request_body = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": openai_compatible_system_message(schema_name),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        started_at = time.perf_counter()
        try:
            with httpx.Client(
                timeout=self._timeout_seconds,
                transport=self._transport,
            ) as client:
                response = client.post(
                    f"{self._base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=request_body,
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMOutputError("openai-compatible provider failed") from exc

        latency_ms = max(0, round((time.perf_counter() - started_at) * 1000))
        try:
            raw_text = extract_chat_completion_content(payload)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMOutputError("openai-compatible provider returned invalid output") from exc

        usage = payload.get("usage", {})
        return LLMResult(
            provider=self.provider,
            model=self.model,
            raw_text=raw_text,
            prompt_tokens=optional_usage_int(usage.get("prompt_tokens")),
            completion_tokens=optional_usage_int(usage.get("completion_tokens")),
            estimated_cost=None,
            latency_ms=latency_ms,
        )


def create_llm_provider(settings: Settings) -> LLMProvider | None:
    if settings.llm_provider == FAKE_LLM_PROVIDER:
        return FakeLLMProvider(model=settings.llm_model or "fake-after-sales-v1")
    if settings.llm_provider == OPENAI_COMPATIBLE_LLM_PROVIDER:
        if not (
            settings.llm_model and settings.openai_api_key and settings.openai_compatible_base_url
        ):
            return None
        return OpenAICompatibleLLMProvider(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_compatible_base_url,
            timeout_seconds=settings.llm_timeout_seconds,
            max_tokens=settings.llm_max_tokens,
            temperature=settings.llm_temperature,
        )
    return None


def openai_compatible_system_message(schema_name: str) -> str:
    return (
        "You are a restricted auxiliary LLM for CommerceFlow Agent. "
        f"Return JSON only matching {schema_name}. "
        "Do not call tools, execute business actions, create approvals, "
        "modify facts, invent policy evidence, or claim refunds/coupons/tickets "
        "were executed."
    )


def extract_chat_completion_content(payload: dict[str, Any]) -> str:
    content = payload["choices"][0]["message"]["content"]
    if not isinstance(content, str) or not content.strip():
        raise ValueError("empty chat completion content")
    return content


def optional_usage_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def parse_intent_candidate(result: LLMResult) -> LLMIntentCandidate:
    try:
        return LLMIntentCandidate.model_validate_json(result.raw_text)
    except (ValidationError, ValueError) as exc:
        raise LLMOutputError("invalid intent extraction output") from exc


def parse_customer_reply(
    result: LLMResult,
    *,
    allowed_policy_ids: set[str],
    allowed_fact_fields: set[str],
) -> LLMCustomerReplyDraft:
    try:
        draft = LLMCustomerReplyDraft.model_validate_json(result.raw_text)
    except (ValidationError, ValueError) as exc:
        raise LLMOutputError("invalid customer reply output") from exc

    unknown_policy_ids = set(draft.cited_policy_ids) - allowed_policy_ids
    unknown_fact_fields = set(draft.cited_fact_fields) - allowed_fact_fields
    if unknown_policy_ids or unknown_fact_fields:
        raise LLMOutputError("customer reply cites unavailable evidence")
    return draft


def estimate_tokens(text: str) -> int:
    return max(1, len(re.findall(r"\w+|[^\s\w]", text, flags=re.UNICODE)) // 2)
