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
  executeActionPlan,
  getActionPlanResult,
  listActionPlans,
} from "../../lib/api";
import {
  displayLabel,
  money,
  recordIdLabel,
  toneForRiskValue,
  toneForStatusValue,
} from "../../lib/display";
import { newIdempotencyKey } from "../../lib/idempotency";
import type {
  ActionPlanExecuteResponse,
  ActionPlanListItem,
  ActionPlanResultResponse,
  ApiError,
} from "../../lib/types";

export default function ToolsPage() {
  const [plans, setPlans] = useState<ActionPlanListItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [idempotencyKey, setIdempotencyKey] = useState("");
  const [execution, setExecution] = useState<ActionPlanExecuteResponse | null>(null);
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
      const executable = response.action_plans.filter(
        (plan) => plan.workflow_status === "awaiting_execution" && plan.planned_tool_name,
      );
      setPlans(executable);
      setSelectedId((current) =>
        executable.some((plan) => plan.action_plan_id === current)
          ? current
          : (executable[0]?.action_plan_id ?? null),
      );
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught : (caught as ApiError));
    } finally {
      setLoading(false);
    }
  }

  async function executeSelected() {
    if (!selected || !idempotencyKey) {
      return;
    }
    setExecuting(true);
    setError(null);
    try {
      const response = await executeActionPlan(selected.action_plan_id, idempotencyKey);
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
      setIdempotencyKey(newIdempotencyKey("web-workflow-execution"));
      void loadPlans();
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <header className="border-b border-line pb-6">
        <p className="text-sm font-semibold uppercase tracking-wide text-signal">持久化工作流</p>
        <h2 className="mt-1 text-3xl font-semibold tracking-tight">本地模拟工具执行</h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
          人工确认后恢复 LangGraph 工作流，由工作流通过 stdio MCP 调用受控工具。页面不会拼装金额、订单号或审批结果。
        </p>
      </header>

      <SafeMockNotice />
      <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
        审批通过只代表允许进入执行确认，不代表已经退款。点击执行仍只创建本地 Mock 记录，不调用真实支付、优惠券或客服系统。
      </div>
      <ErrorNotice error={error} />

      <div className="grid gap-6 xl:grid-cols-[420px_1fr]">
        <Panel title="等待执行确认的动作计划" eyebrow={loading ? "加载中" : `${plans.length} 条`}>
          {loading ? (
            <EmptyState message="正在加载持久化动作计划..." />
          ) : plans.length === 0 ? (
            <EmptyState message="当前没有等待执行确认的动作计划。请先在审批中心批准高风险计划，或创建低额补偿计划。" />
          ) : (
            <div className="grid gap-3">
              {plans.map((plan) => (
                <button
                  key={plan.action_plan_id}
                  type="button"
                  onClick={() => {
                    setSelectedId(plan.action_plan_id);
                    setExecution(null);
                    setResult(null);
                    setError(null);
                  }}
                  className={`rounded-lg border p-4 text-left ${
                    plan.action_plan_id === selectedId
                      ? "border-signal bg-teal-50"
                      : "border-line bg-white hover:border-signal"
                  }`}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={toneForStatusValue(plan.workflow_status)}>
                      {displayLabel(plan.workflow_status)}
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

        <Panel title="执行确认" eyebrow="人工触发 Graph Resume">
          {!selected ? (
            <EmptyState message="请选择一个等待执行确认的动作计划。" />
          ) : (
            <div className="space-y-5">
              <dl className="grid gap-4 md:grid-cols-2">
                <KeyValue label="动作计划 ID" value={selected.action_plan_id} />
                <KeyValue label="运行 ID" value={selected.run_id} />
                <KeyValue label="审批 ID" value={selected.approval_id ?? "无需审批"} />
                <KeyValue
                  label="工作流状态"
                  value={displayLabel(selected.workflow_status)}
                  raw={selected.workflow_status}
                />
                <KeyValue
                  label="计划工具"
                  value={displayLabel(selected.planned_tool_name)}
                  raw={selected.planned_tool_name}
                />
                <KeyValue label="金额" value={money(selected.proposed_amount, selected.currency)} />
              </dl>

              <div className="rounded-lg border border-sky-200 bg-sky-50 p-4 text-sm leading-6 text-sky-950">
                执行参数将由后端从已持久化的动作计划生成，LLM 和浏览器都不能改写订单号、金额、审批 ID 或政策依据。
              </div>

              <IdempotencyKeyBox
                value={idempotencyKey}
                onRefresh={() => {
                  setIdempotencyKey(newIdempotencyKey("web-workflow-execution"));
                  setExecution(null);
                  setResult(null);
                }}
              />

              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  disabled={executing || !idempotencyKey}
                  onClick={() => void executeSelected()}
                  className="rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                >
                  {executing
                    ? "正在恢复工作流并调用 MCP..."
                    : execution
                      ? "使用相同幂等键重试"
                      : "确认执行本地模拟工具"}
                </button>
                <Link
                  href={`/cases/${selected.action_plan_id}`}
                  className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
                >
                  查看案例详情
                </Link>
              </div>

              {execution ? <ExecutionResult execution={execution} result={result} /> : null}
              <DebugJson
                title="工作流恢复请求 JSON"
                data={{
                  action_plan_id: selected.action_plan_id,
                  confirm: true,
                  idempotency_key: idempotencyKey,
                }}
              />
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}

function ExecutionResult({
  execution,
  result,
}: {
  execution: ActionPlanExecuteResponse;
  result: ActionPlanResultResponse | null;
}) {
  return (
    <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="success">{displayLabel(execution.tool_name)}</Badge>
        <Badge tone="success">{displayLabel(execution.workflow_status)}</Badge>
        <Badge tone={execution.idempotent_replay ? "warning" : "success"}>
          {execution.idempotent_replay ? "幂等重放" : "首次执行"}
        </Badge>
      </div>
      <dl className="mt-4 grid gap-3 md:grid-cols-2">
        <KeyValue label="记录 ID" value={execution.record_id} />
        <KeyValue label="动作计划 ID" value={execution.action_plan_id} />
        <KeyValue label="运行 ID" value={execution.run_id} />
        <KeyValue label="执行状态" value={displayLabel(execution.execution_status)} />
        <KeyValue label="Trace ID" value={execution.trace_id ?? "未启用 Trace"} />
        <KeyValue
          label={recordIdLabel(result?.result_type)}
          value={result?.result ? recordId(result.result) : "正在等待结果查询"}
        />
      </dl>
      <DebugJson title="本地模拟结果调试 JSON" data={result ?? execution} />
    </div>
  );
}

function recordId(result: Record<string, unknown>): string {
  return String(result.refund_id ?? result.coupon_id ?? result.ticket_id ?? "无");
}
