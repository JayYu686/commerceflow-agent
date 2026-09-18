import json
import math
import time

import httpx

from commerceflow.config import settings
from commerceflow.db import DomainError, identifier, lock, transaction
from commerceflow.models import BudgetAccount, ModelCall


def reserve(case_id, request):
    cfg = settings()
    provider = cfg.model_provider
    call_id = identifier()
    # UTF-8 bytes bound ordinary text tokenization conservatively. Add a protocol
    # allowance for chat/tool framing; outputs include the complete capped response.
    input_bound = len(json.dumps(request, ensure_ascii=False).encode("utf-8")) + 4096
    maximum = (
        math.ceil(
            input_bound * cfg.deepseek_input_per_million
            + cfg.max_output_tokens * cfg.deepseek_output_per_million
        )
        if provider == "deepseek"
        else 0
    )
    with transaction() as session:
        if provider == "deepseek":
            lock(session, "deepseek-budget")
            account = session.get(BudgetAccount, "deepseek")
            if not account:
                account = BudgetAccount(id="deepseek", committed_microyuan=0)
                session.add(account)
            if account.committed_microyuan + maximum > cfg.budget_admission_fen * 10000:
                raise DomainError("budget_exhausted", "DeepSeek预算不足，已停止新调用")
            account.committed_microyuan += maximum
        session.add(
            ModelCall(
                id=call_id,
                case_id=case_id,
                provider=provider,
                model="deepseek-flash" if provider == "deepseek" else cfg.model_name,
                reserved_microyuan=maximum,
                pricing={
                    "date": cfg.pricing_date,
                    "input_per_million": cfg.deepseek_input_per_million,
                    "output_per_million": cfg.deepseek_output_per_million,
                    "input_token_bound": input_bound,
                },
            )
        )
    return call_id


def complete(case_id, messages, tools):
    cfg = settings()
    if cfg.model_provider not in {"qwen", "deepseek"}:
        raise DomainError("invalid_provider", "必须显式选择qwen或deepseek")
    paid = cfg.model_provider == "deepseek"
    body = {
        "model": "deepseek-flash" if paid else cfg.model_name,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0.7,
        "top_p": 0.8,
        "max_tokens": cfg.max_output_tokens,
    }
    if paid:
        body["thinking"] = {"type": "disabled"}
    else:
        body["chat_template_kwargs"] = {"enable_thinking": False}
    key = cfg.deepseek_key.get_secret_value() if paid else cfg.model_key.get_secret_value()
    if paid and not key:
        raise DomainError("missing_model_key", "DeepSeek密钥未配置")
    call_id = reserve(case_id, body)
    started = time.monotonic()
    try:
        base = "https://api.deepseek.com" if paid else cfg.model_url.rstrip("/")
        with httpx.Client(timeout=cfg.model_timeout, trust_env=False) as client:
            response = client.post(
                base + "/chat/completions", json=body, headers={"Authorization": "Bearer " + key}
            )
            response.raise_for_status()
            result = response.json()
        with transaction() as session:
            row = session.get(ModelCall, call_id)
            row.status = "completed"
            row.model = result.get("model", row.model)
            row.usage = result.get("usage")
            row.elapsed_ms = round((time.monotonic() - started) * 1000)
            if row.usage and paid:
                usage = row.usage
                # Use worst-price input including cached tokens: a conservative
                # expenditure estimate, never claim this is the provider invoice.
                cost = math.ceil(
                    usage["prompt_tokens"] * cfg.deepseek_input_per_million
                    + usage["completion_tokens"] * cfg.deepseek_output_per_million
                )
                lock(session, "deepseek-budget")
                account = session.get(BudgetAccount, "deepseek")
                account.committed_microyuan += cost - row.reserved_microyuan
                row.actual_microyuan = cost
        return result["choices"][0]["message"]
    except Exception:
        with transaction() as session:
            row = session.get(ModelCall, call_id)
            row.status = "usage_unknown"
            row.elapsed_ms = round((time.monotonic() - started) * 1000)
        raise
