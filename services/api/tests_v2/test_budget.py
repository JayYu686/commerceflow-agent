from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select

from commerceflow.config import settings
from commerceflow.db import DomainError, transaction
from commerceflow.llm import reserve
from commerceflow.models import BudgetAccount, ModelCall


def test_budget_admission_is_atomic_and_unknown_usage_stays_reserved(db, monkeypatch):
    monkeypatch.setenv("CF_MODEL_PROVIDER", "deepseek")
    monkeypatch.setenv("CF_BUDGET_ADMISSION_FEN", "1")
    settings.cache_clear()
    # Even one request's output + framing allowance exceeds one fen; none may start.
    try:

        def attempt(_index):
            try:
                reserve(None, {"messages": [{"role": "user", "content": "hello"}]})
                return True
            except DomainError as exc:
                assert exc.code == "budget_exhausted"
                return False

        with ThreadPoolExecutor(max_workers=4) as pool:
            assert not any(pool.map(attempt, range(8)))
        monkeypatch.setenv("CF_BUDGET_ADMISSION_FEN", "3")
        settings.cache_clear()
        with ThreadPoolExecutor(max_workers=4) as pool:
            accepted = list(pool.map(attempt, range(8)))
        assert sum(accepted) == 1
        with transaction() as session:
            account = session.get(BudgetAccount, "deepseek")
            call = session.scalar(select(ModelCall))
            assert account.committed_microyuan == call.reserved_microyuan
            assert call.actual_microyuan is None
    finally:
        monkeypatch.setenv("CF_MODEL_PROVIDER", "qwen")
        monkeypatch.delenv("CF_BUDGET_ADMISSION_FEN")
        settings.cache_clear()
