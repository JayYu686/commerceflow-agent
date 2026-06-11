"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "../../components/console/Badge";
import { DebugJson } from "../../components/console/DebugJson";
import { EmptyState } from "../../components/console/EmptyState";
import { ErrorNotice } from "../../components/console/ErrorNotice";
import { IdempotencyKeyBox } from "../../components/console/IdempotencyKeyBox";
import { KeyValue } from "../../components/console/KeyValue";
import { Panel } from "../../components/console/Panel";
import { SafeMockNotice } from "../../components/console/SafeMockNotice";
import {
  executeCouponIssue,
  executeRefundApply,
  executeTicketCreate,
  getActionPlanResult,
  listActionPlans,
} from "../../lib/api";
import {
  displayLabel,
  formatDateTime,
  money,
  recordIdLabel,
  toneForRiskValue,
  toneForStatusValue,
} from "../../lib/display";
import { newIdempotencyKey } from "../../lib/idempotency";
import type {
  ActionPlanListItem,
  ActionPlanResultResponse,
  ApiError,
  CouponIssueRequest,
  RefundApplyRequest,
  TicketCreateRequest,
  ToolExecutionResponse,
} from "../../lib/types";

export default function ToolsPage() {
  const [plans, setPlans] = useState<ActionPlanListItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [ticketCategory, setTicketCategory] = useState("manual_review");
  const [ticketSummary, setTicketSummary] = useState("");
  const [idempotencyKey, setIdempotencyKey] = useState("");
  const [execution, setExecution] = useState<ToolExecutionResponse | null>(null);
  const [result, setResult] = useState<ActionPlanResultResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState(false);
  const [error, setError] = useState<ApiError | Error | null>(null);

  const selected = useMemo(
    () => plans.find((plan) => plan.action_plan_id === selectedId) ?? null,
    [plans, selectedId],
  );

  async function loadPlans() {
    setLoading(true);
    setError(null);
    try {
      const response = await listActionPlans({ execution_status: "not_executed", limit: 100 });
      const executable = response.action_plans.filter((plan) => plan.planned_tool_name);
      setPlans(executable);
      const next = executable[0] ?? null;
      setSelectedId(next?.action_plan_id ?? null);
      initializeForm(next);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught : (caught as ApiError));
    } finally {
      setLoading(false);
    }
  }

  function choosePlan(plan: ActionPlanListItem) {
    setSelectedId(plan.action_plan_id);
    initializeForm(plan);
    setExecution(null);
    setResult(null);
    setError(null);
  }

  function initializeForm(plan: ActionPlanListItem | null) {
    setReason(defaultReason(plan));
    setTicketCategory(plan?.intent ?? "manual_review");
    setTicketSummary(plan?.summary ?? "Create follow-up ticket for manual review.");
  }

  async function executeSelected() {
    if (!selected || !idempotencyKey) {
      return;
    }
    setExecuting(true);
    setError(null);
    try {
      const response = await executeForPlan(selected, reason, ticketCategory, ticketSummary, idempotencyKey);
      setExecution(response);
      setResult(await getActionPlanResult(selected.action_plan_id));
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught : (caught as ApiError));
    } finally {
      setExecuting(false);
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setIdempotencyKey(newIdempotencyKey("web-tool-execution"));
      void loadPlans();
    }, 0);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <header className="border-b border-line pb-6">
        <p className="text-sm font-semibold uppercase tracking-wide text-signal">Phase 5B</p>
        <h2 className="mt-1 text-3xl font-semibold tracking-tight">Mock 工具执行</h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
          手动执行已计划或已批准的本地 Mock Tool。Agent 不会自动调用这些接口，LLM 也不能决定工具执行。
        </p>
      </header>

      <SafeMockNotice />
      <ErrorNotice error={error} />

      <div className="grid gap-6 xl:grid-cols-[420px_1fr]">
        <Panel title="可执行 Action Plan" eyebrow={loading ? "加载中" : `${plans.length} 条`}>
          {loading ? (
            <EmptyState message="正在加载可执行动作计划..." />
          ) : plans.length === 0 ? (
            <EmptyState message="当前没有 not_executed 且带 planned tool 的 Action Plan。可以先从工作台创建计划，或在审批中心批准高风险计划。" />
          ) : (
            <div className="grid gap-3">
              {plans.map((plan) => (
                <button
                  key={plan.action_plan_id}
                  type="button"
                  onClick={() => choosePlan(plan)}
                  className={`rounded-lg border p-4 text-left ${
                    plan.action_plan_id === selectedId
                      ? "border-signal bg-teal-50"
                      : "border-line bg-white hover:border-signal"
                  }`}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={toneForStatusValue(plan.status)}>{displayLabel(plan.status)}</Badge>
                    <Badge tone={toneForStatusValue(plan.execution_status)}>
                      {displayLabel(plan.execution_status)}
                    </Badge>
                    <Badge tone={toneForRiskValue(plan.risk_level)}>
                      {displayLabel(plan.risk_level)}
                    </Badge>
                  </div>
                  <div className="mt-2 break-all text-sm font-semibold">{plan.action_plan_id}</div>
                  <div className="mt-1 text-sm text-slate-600">
                    {displayLabel(plan.planned_tool_name)} · {plan.order_no ?? "无订单"} ·{" "}
                    {money(plan.proposed_amount, plan.currency)}
                  </div>
                </button>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="执行面板" eyebrow="人工触发 Mock Tool">
          {!selected ? (
            <EmptyState message="请选择一个可执行 Action Plan。" />
          ) : (
            <div className="space-y-5">
              <div className="grid gap-4 md:grid-cols-2">
                <KeyValue label="Action Plan ID" value={selected.action_plan_id} />
                <KeyValue label="Approval ID" value={selected.approval_id ?? "无"} />
                <KeyValue label="计划工具" value={displayLabel(selected.planned_tool_name)} raw={selected.planned_tool_name} />
                <KeyValue label="状态" value={displayLabel(selected.status)} raw={selected.status} />
                <KeyValue label="订单号" value={selected.order_no ?? "无"} />
                <KeyValue label="金额" value={money(selected.proposed_amount, selected.currency)} />
              </div>

              <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
                前端只提供人工触发入口。refund 和高额 coupon 是否可执行，仍由后端工具服务检查审批、金额、订单、
                policy evidence、幂等键和重复执行状态。
              </div>

              <IdempotencyKeyBox
                value={idempotencyKey}
                onRefresh={() => {
                  setIdempotencyKey(newIdempotencyKey("web-tool-execution"));
                  setExecution(null);
                  setResult(null);
                }}
              />

              {selected.planned_tool_name === "ticket_create" ? (
                <>
                  <label className="block text-sm">
                    <span className="font-medium text-slate-700">工单类别</span>
                    <input
                      value={ticketCategory}
                      onChange={(event) => setTicketCategory(event.target.value)}
                      className="mt-2 w-full rounded-md border border-line bg-white px-3 py-2"
                    />
                  </label>
                  <label className="block text-sm">
                    <span className="font-medium text-slate-700">工单摘要</span>
                    <textarea
                      value={ticketSummary}
                      onChange={(event) => setTicketSummary(event.target.value)}
                      rows={4}
                      className="mt-2 w-full rounded-md border border-line bg-white px-3 py-2"
                    />
                  </label>
                </>
              ) : (
                <label className="block text-sm">
                  <span className="font-medium text-slate-700">执行原因</span>
                  <textarea
                    value={reason}
                    onChange={(event) => setReason(event.target.value)}
                    rows={4}
                    className="mt-2 w-full rounded-md border border-line bg-white px-3 py-2"
                  />
                </label>
              )}

              <button
                type="button"
                disabled={executing || !idempotencyKey || !canExecuteClientSide(selected)}
                onClick={() => void executeSelected()}
                className="rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300"
              >
                {executing ? "正在执行 Mock Tool..." : execution ? "使用相同幂等键重试" : "执行 Mock Tool"}
              </button>

              {!canExecuteClientSide(selected) ? (
                <div className="text-sm text-amber-800">
                  该计划当前状态不适合从前端直接执行。后端仍会做最终安全校验。
                </div>
              ) : null}

              {execution ? <ExecutionResult execution={execution} result={result} /> : null}
              <DebugJson
                title="工具请求预览 JSON"
                data={selected ? buildPreviewPayload(selected, reason, ticketCategory, ticketSummary) : {}}
              />
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}

async function executeForPlan(
  plan: ActionPlanListItem,
  reason: string,
  ticketCategory: string,
  ticketSummary: string,
  idempotencyKey: string,
): Promise<ToolExecutionResponse> {
  if (plan.planned_tool_name === "refund_apply") {
    const request: RefundApplyRequest = {
      action_plan_id: plan.action_plan_id,
      approval_id: plan.approval_id ?? "",
      order_no: plan.order_no ?? "",
      amount: plan.proposed_amount ?? "0.00",
      currency: plan.currency ?? "CNY",
      reason,
    };
    return executeRefundApply(request, idempotencyKey);
  }

  if (plan.planned_tool_name === "coupon_issue") {
    const request: CouponIssueRequest = {
      action_plan_id: plan.action_plan_id,
      approval_id: plan.approval_id,
      order_no: plan.order_no ?? "",
      amount: plan.proposed_amount ?? "0.00",
      currency: plan.currency ?? "CNY",
      reason,
    };
    return executeCouponIssue(request, idempotencyKey);
  }

  const request: TicketCreateRequest = {
    action_plan_id: plan.action_plan_id,
    order_no: plan.order_no ?? "",
    category: ticketCategory,
    summary: ticketSummary,
  };
  return executeTicketCreate(request, idempotencyKey);
}

function buildPreviewPayload(
  plan: ActionPlanListItem,
  reason: string,
  ticketCategory: string,
  ticketSummary: string,
) {
  if (plan.planned_tool_name === "ticket_create") {
    return {
      action_plan_id: plan.action_plan_id,
      order_no: plan.order_no,
      category: ticketCategory,
      summary: ticketSummary,
    };
  }
  return {
    action_plan_id: plan.action_plan_id,
    approval_id: plan.approval_id,
    order_no: plan.order_no,
    amount: plan.proposed_amount,
    currency: plan.currency,
    reason,
  };
}

function canExecuteClientSide(plan: ActionPlanListItem): boolean {
  return (
    plan.execution_status === "not_executed" &&
    Boolean(plan.planned_tool_name) &&
    plan.status !== "pending_approval" &&
    plan.status !== "rejected" &&
    plan.status !== "not_executable"
  );
}

function defaultReason(plan: ActionPlanListItem | null): string {
  if (!plan) {
    return "";
  }
  if (plan.planned_tool_name === "refund_apply") {
    return "Quality issue refund approved for local mock execution.";
  }
  if (plan.planned_tool_name === "coupon_issue") {
    return "Delay compensation for local mock execution.";
  }
  return plan.summary;
}

function ExecutionResult({
  execution,
  result,
}: {
  execution: ToolExecutionResponse;
  result: ActionPlanResultResponse | null;
}) {
  return (
    <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="success">{displayLabel(execution.tool_name)}</Badge>
        <Badge tone="success">{displayLabel(execution.status)}</Badge>
        <Badge tone={execution.idempotent_replay ? "warning" : "success"}>
          {execution.idempotent_replay ? "幂等重放" : "首次执行"}
        </Badge>
      </div>
      <dl className="mt-4 grid gap-3 md:grid-cols-2">
        <KeyValue label="Record ID" value={execution.record_id} />
        <KeyValue label="Action Plan ID" value={execution.action_plan_id} />
        <KeyValue label="订单号" value={execution.order_no} />
        <KeyValue label="执行状态" value={displayLabel(execution.execution_status)} />
        <KeyValue label="创建时间" value={formatDateTime(execution.created_at)} />
        <KeyValue
          label={recordIdLabel(result?.result_type)}
          value={result?.result ? recordId(result.result as unknown as Record<string, unknown>) : "正在等待结果查询"}
        />
      </dl>
      <DebugJson title="Mock Result 调试 JSON" data={result ?? execution} />
    </div>
  );
}

function recordId(result: Record<string, unknown>): string {
  return String(result.refund_id ?? result.coupon_id ?? result.ticket_id ?? "无");
}
