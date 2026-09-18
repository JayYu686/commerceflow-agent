import hmac
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header
from fastapi.responses import JSONResponse
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from commerceflow.config import settings
from commerceflow.db import DomainError, digest, identifier, lock, transaction
from commerceflow.models import BusinessResult, Order, OrderItem, Ticket


def authorize(token, write=False):
    secret = settings().commerce_write_token if write else settings().commerce_read_token
    if not secret.get_secret_value() or not hmac.compare_digest(
        token or "", secret.get_secret_value()
    ):
        raise DomainError("unauthorized", "Invalid service credential", 401)


def require_writer(authorization: str = Header(default="")):
    authorize(authorization.removeprefix("Bearer "), write=True)


def order_snapshot(order_no):
    with transaction(True) as session:
        order = session.get(Order, order_no)
        if not order:
            raise DomainError("order_not_found", "订单不存在", 404)
        items = list(session.scalars(select(OrderItem).where(OrderItem.order_no == order_no)))
        return {
            "order_no": order.order_no,
            "customer_id": order.customer_id,
            "status": order.status,
            "paid_fen": order.paid_fen,
            "refunded_fen": order.refunded_fen,
            "paid_at": order.paid_at.isoformat(),
            "delivered_at": order.delivered_at.isoformat() if order.delivered_at else None,
            "promised_at": order.promised_at.isoformat(),
            "tracking_no": order.tracking_no,
            "carrier_events": order.carrier_events,
            "items": [
                {
                    "id": i.id,
                    "name": i.name,
                    "category": i.category,
                    "aftersales_type": i.aftersales_type,
                    "paid_fen": i.paid_fen,
                    "refunded_fen": i.refunded_fen,
                }
                for i in items
            ],
        }


def history_snapshot(order_no):
    with transaction(True) as session:
        rows = session.scalars(select(BusinessResult).where(BusinessResult.order_no == order_no))
        return {"results": [{"entitlement_key": r.entitlement_key, **r.payload} for r in rows]}


class WriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    execution_id: str
    case_id: str
    plan_checksum: str
    order_no: str
    item_id: str | None
    intent: str
    amount_fen: int = Field(gt=0)
    entitlement_key: str
    approved: bool
    confirmed: bool


def execute_business(request: WriteRequest):
    body = request.model_dump()
    request_hash = digest(body)
    with transaction(True) as session:
        lock(session, "execution:" + request.execution_id)
        existing = session.get(BusinessResult, request.execution_id)
        if existing:
            if existing.request_hash != request_hash:
                raise DomainError("idempotency_conflict", "执行ID已经绑定不同请求")
            return existing.payload
        order = session.scalar(
            select(Order).where(Order.order_no == request.order_no).with_for_update()
        )
        if not order:
            raise DomainError("order_not_found", "订单不存在", 404)
        if (
            not request.confirmed
            or (
                request.intent == "quality_issue_refund"
                or request.amount_fen > settings().approval_threshold_fen
            )
            and not request.approved
        ):
            raise DomainError("authorization_required", "缺少执行确认或审核授权", 403)
        if order.status == "cancelled" or order.paid_fen <= 0:
            raise DomainError("ineligible_order", "订单状态不允许执行")
        if request.intent == "quality_issue_refund":
            item = session.get(OrderItem, request.item_id)
            if not item or item.order_no != request.order_no:
                raise DomainError("item_mismatch", "商品不属于该订单")
            entitlement = f"refund:{item.id}"
            if request.amount_fen != item.paid_fen - item.refunded_fen:
                raise DomainError("amount_changed", "商品剩余可退款金额已改变")
            item.refunded_fen += request.amount_fen
            order.refunded_fen += request.amount_fen
            if order.refunded_fen > order.paid_fen:
                raise DomainError("refund_limit", "累计退款超过订单实付")
            if order.refunded_fen == order.paid_fen:
                order.status = "refunded"
            resolution = "refund_succeeded"
        elif request.intent == "logistics_delay_compensation":
            entitlement = f"delay:{order.order_no}"
            if request.amount_fen != settings().coupon_fen or request.item_id is not None:
                raise DomainError("amount_mismatch", "补偿金额与配置不一致")
            resolution = "coupon_issued"
        else:
            raise DomainError("unsupported_action", "不支持此操作")
        if entitlement != request.entitlement_key:
            raise DomainError("entitlement_mismatch", "权益标识不匹配")
        if session.scalar(
            select(BusinessResult).where(BusinessResult.entitlement_key == entitlement)
        ):
            raise DomainError("already_processed", "权益已经领取")
        ticket_id = identifier()
        result = {
            "execution_id": request.execution_id,
            "order_no": order.order_no,
            "item_id": request.item_id,
            "amount_fen": request.amount_fen,
            "status": "succeeded",
            "resolution": resolution,
            "ticket_id": ticket_id,
            "coupon_code": "CF-" + request.execution_id[:12]
            if resolution == "coupon_issued"
            else None,
            "order_refunded_fen": order.refunded_fen,
            "simulated": True,
        }
        session.add(
            BusinessResult(
                execution_id=request.execution_id,
                entitlement_key=entitlement,
                request_hash=request_hash,
                order_no=order.order_no,
                payload=result,
            )
        )
        session.flush()
        session.add(
            Ticket(
                id=ticket_id,
                execution_id=request.execution_id,
                case_id=request.case_id,
                order_no=order.order_no,
                resolution=resolution,
            )
        )
        return result


mcp = FastMCP(
    "CommerceFlow commerce facts",
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(
        allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*", "commerce:8001"],
        allowed_origins=[],
    ),
)


@mcp.tool()
def get_order(order_no: str) -> dict:
    """Read authoritative paid amounts, items, delivery and shipment facts."""
    return order_snapshot(order_no)


@mcp.tool()
def get_shipment(order_no: str) -> dict:
    """Read carrier events, delivery time and promised delivery time."""
    data = order_snapshot(order_no)
    return {
        key: data[key]
        for key in ("order_no", "tracking_no", "carrier_events", "delivered_at", "promised_at")
    }


@mcp.tool()
def get_aftersales_history(order_no: str) -> dict:
    """Read previously consumed refund and compensation entitlements."""
    return history_snapshot(order_no)


@asynccontextmanager
async def lifespan(_app):
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="CommerceFlow simulated commerce", lifespan=lifespan)


@app.middleware("http")
async def service_auth(request, call_next):
    if request.url.path.startswith("/tools"):
        try:
            authorize(request.headers.get("authorization", "").removeprefix("Bearer "))
        except DomainError as exc:
            return JSONResponse({"code": exc.code, "message": exc.message}, status_code=exc.status)
    return await call_next(request)


@app.exception_handler(DomainError)
async def error_handler(_request, exc):
    return JSONResponse({"code": exc.code, "message": exc.message}, status_code=exc.status)


@app.get("/health")
def health():
    return {"status": "ok", "simulated": True}


@app.post("/executions", dependencies=[Depends(require_writer)])
def execute(request: WriteRequest):
    return execute_business(request)


@app.get("/executions/{execution_id}", dependencies=[Depends(require_writer)])
def execution_result(execution_id: str):
    with transaction(True) as session:
        result = session.get(BusinessResult, execution_id)
        if not result:
            raise DomainError("not_found", "执行记录不存在", 404)
        return result.payload


app.mount("/tools", mcp.streamable_http_app())
