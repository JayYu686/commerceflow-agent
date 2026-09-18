import asyncio
import hashlib
import hmac
import json
from datetime import timedelta

from fastapi import Depends, FastAPI, Header, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text

from commerceflow import cases
from commerceflow.config import settings
from commerceflow.db import DomainError, transaction, utcnow
from commerceflow.models import Case, Event, Execution, LoginSession, ModelCall

app = FastAPI(title="CommerceFlow Agent", version="2.0.0")


@app.exception_handler(DomainError)
async def error_handler(_request, exc):
    return JSONResponse({"code": exc.code, "message": exc.message}, status_code=exc.status)


@app.middleware("http")
async def same_origin_writes(request, call_next):
    if (
        request.method in {"POST", "PUT", "PATCH", "DELETE"}
        and request.headers.get("x-requested-with") != "CommerceFlow"
    ):
        return JSONResponse(
            {"code": "csrf_header_required", "message": "Missing application header"},
            status_code=403,
        )
    return await call_next(request)


def actor(request: Request):
    token = request.cookies.get("cf_session", "")
    with transaction() as session:
        login = session.get(LoginSession, hashlib.sha256(token.encode()).hexdigest())
        if not token or not login or login.expires_at <= utcnow():
            raise DomainError("login_required", "请先登录演示账号", 401)
        return login.role


def operator(role=Depends(actor)):
    if role != "operator":
        raise DomainError("forbidden", "此操作需要客服身份", 403)
    return role


def reviewer(role=Depends(actor)):
    if role != "reviewer":
        raise DomainError("forbidden", "此操作需要审核员身份", 403)
    return role


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(Input):
    role: str
    password: str


class Message(Input):
    content: str = Field(min_length=1, max_length=6000)


class Decision(Input):
    approved: bool
    comment: str = Field(min_length=4, max_length=2000)
    evidence_checked: bool


class Confirmation(Input):
    confirmed: bool


@app.get("/health")
def health():
    with transaction() as session:
        session.execute(text("SELECT 1"))
    return {"status": "ok", "version": "2.0.0", "simulated": True}


@app.post("/api/session")
def login(body: Login, response: Response, idempotency_key: str = Header(alias="Idempotency-Key")):
    cfg = settings()
    password = {"operator": cfg.operator_password, "reviewer": cfg.reviewer_password}.get(body.role)
    if (
        not password
        or not password.get_secret_value()
        or not hmac.compare_digest(body.password.encode(), password.get_secret_value().encode())
    ):
        raise DomainError("invalid_credentials", "账号或密码错误", 401)
    if not idempotency_key or len(idempotency_key) > 100:
        raise DomainError("invalid_idempotency_key", "需要1到100字符的幂等键", 400)
    token = hmac.new(
        password.get_secret_value().encode(),
        (body.role + ":" + idempotency_key).encode(),
        hashlib.sha256,
    ).hexdigest()
    with transaction() as session:
        # Login never persists the password or raw session token in a replay record.
        from commerceflow.db import lock

        token_hash = hashlib.sha256(token.encode()).hexdigest()
        lock(session, "login:" + token_hash)
        login_session = session.get(LoginSession, token_hash)
        if login_session is None:
            session.add(
                LoginSession(
                    token_hash=token_hash, role=body.role, expires_at=utcnow() + timedelta(hours=8)
                )
            )
        elif login_session.expires_at <= utcnow():
            raise DomainError("login_request_expired", "请发起新的登录请求", 401)
    response.set_cookie(
        "cf_session",
        token,
        httponly=True,
        samesite="strict",
        secure=cfg.cookie_secure,
        max_age=28800,
        path="/",
    )
    return {"role": body.role}


@app.get("/api/session")
def whoami(role=Depends(actor)):
    return {"role": role, "model": settings().model_name, "provider": settings().model_provider}


@app.post("/api/logout")
def logout(
    request: Request,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    with transaction() as session:
        row = session.get(
            LoginSession, hashlib.sha256(request.cookies.get("cf_session", "").encode()).hexdigest()
        )
        if row:
            row.expires_at = min(row.expires_at, utcnow())
    response.delete_cookie("cf_session", path="/")
    return {"status": "logged_out"}


@app.post("/api/cases")
def create(
    body: Message, role=Depends(operator), idempotency_key: str = Header(alias="Idempotency-Key")
):
    with transaction() as session:
        return cases.idempotent(
            session,
            role,
            "create",
            idempotency_key,
            body.model_dump(),
            lambda: cases.create_case(session, body.content, role),
        )


@app.post("/api/cases/{case_id}/messages")
def message(
    case_id: str,
    body: Message,
    role=Depends(operator),
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    with transaction() as session:
        return cases.idempotent(
            session,
            role,
            "message:" + case_id,
            idempotency_key,
            body.model_dump(),
            lambda: cases.add_message(session, case_id, body.content, role),
        )


@app.get("/api/cases")
def list_cases(_role=Depends(actor)):
    with transaction() as session:
        rows = session.scalars(
            select(Case)
            .where(Case.owner != "evaluation")
            .order_by(Case.created_at.desc())
            .limit(100)
        )
        return [{"id": c.id, "status": c.status, "order_no": c.order_no} for c in rows]


@app.get("/api/cases/{case_id}")
def get_case(case_id: str, _role=Depends(actor)):
    with transaction() as session:
        return cases.case_view(session, case_id)


@app.post("/api/plans/{plan_id}/approval")
def approve(
    plan_id: str,
    body: Decision,
    role=Depends(reviewer),
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    if body.approved and not body.evidence_checked:
        raise DomainError("evidence_review_required", "请先核实证据及排除条款", 400)
    with transaction() as session:
        return cases.idempotent(
            session,
            role,
            "approve:" + plan_id,
            idempotency_key,
            body.model_dump(),
            lambda: cases.approve(session, plan_id, body.approved, body.comment, role),
        )


@app.post("/api/plans/{plan_id}/confirmation")
def confirm(
    plan_id: str,
    body: Confirmation,
    role=Depends(operator),
    idempotency_key: str = Header(alias="Idempotency-Key"),
):
    if not body.confirmed:
        raise DomainError("confirmation_required", "必须明确确认执行", 400)
    with transaction() as session:
        return cases.idempotent(
            session,
            role,
            "confirm:" + plan_id,
            idempotency_key,
            body.model_dump(),
            lambda: cases.confirm(session, plan_id, role),
        )


@app.get("/api/executions/{execution_id}")
def execution(execution_id: str, _role=Depends(actor)):
    with transaction() as session:
        row = session.get(Execution, execution_id)
        if not row:
            raise DomainError("not_found", "执行不存在", 404)
        return {"id": row.id, "status": row.status, "result": row.result}


@app.get("/api/cases/{case_id}/events")
async def events(
    case_id: str,
    request: Request,
    _role=Depends(actor),
    last_event_id: str = Header(default="0", alias="Last-Event-ID"),
):
    try:
        cursor = max(0, int(last_event_id))
    except ValueError as exc:
        raise DomainError("invalid_cursor", "无效的事件游标", 400) from exc
    with transaction() as session:
        cases.get_case(session, case_id)

    async def stream():
        nonlocal cursor
        while not await request.is_disconnected():
            with transaction() as session:
                rows = list(
                    session.scalars(
                        select(Event)
                        .where(Event.case_id == case_id, Event.id > cursor)
                        .order_by(Event.id)
                        .limit(100)
                    )
                )
            for row in rows:
                cursor = row.id
                data = json.dumps(
                    {
                        "id": row.id,
                        "kind": row.kind,
                        "payload": row.payload,
                        "at": row.created_at.isoformat(),
                    },
                    ensure_ascii=False,
                )
                yield f"id: {row.id}\ndata: {data}\n\n"
            if not rows:
                yield ": heartbeat\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/budget")
def budget(_role=Depends(actor)):
    with transaction() as session:
        rows = list(session.scalars(select(ModelCall).where(ModelCall.provider == "deepseek")))
        amount = sum(
            r.actual_microyuan if r.actual_microyuan is not None else r.reserved_microyuan
            for r in rows
        )
        return {
            "committed_yuan": amount / 1_000_000,
            "admission_limit_yuan": 25,
            "task_budget_yuan": 30,
            "calls": len(rows),
        }
