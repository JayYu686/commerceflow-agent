"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "../../../components/console/Badge";
import { DebugJson } from "../../../components/console/DebugJson";
import { EmptyState } from "../../../components/console/EmptyState";
import { ErrorNotice } from "../../../components/console/ErrorNotice";
import { KeyValue } from "../../../components/console/KeyValue";
import { Panel } from "../../../components/console/Panel";
import { SafeMockNotice } from "../../../components/console/SafeMockNotice";
import { getActionPlan, getActionPlanAuditLogs, getActionPlanResult } from "../../../lib/api";
import {
  displayLabel,
  formatDateTime,
  money,
  recordIdLabel,
  toneForRiskValue,
  toneForStatusValue,
  yesNo,
} from "../../../lib/display";
import type {
  ActionPlanResponse,
  ActionPlanResultResponse,
  ApiError,
  AuditLogEvent,
} from "../../../lib/types";

export default function CaseDetailPage() {
  const params = useParams<{ actionPlanId: string }>();
  const actionPlanId = Array.isArray(params.actionPlanId)
    ? params.actionPlanId[0]
    : params.actionPlanId;
  const [actionPlan, setActionPlan] = useState<ActionPlanResponse | null>(null);
  const [result, setResult] = useState<ActionPlanResultResponse | null>(null);
  const [events, setEvents] = useState<AuditLogEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | Error | null>(null);

  async function loadCase() {
    if (!actionPlanId) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [planResponse, resultResponse, auditResponse] = await Promise.all([
        getActionPlan(actionPlanId),
        getActionPlanResult(actionPlanId),
        getActionPlanAuditLogs(actionPlanId),
      ]);
      setActionPlan(planResponse);
      setResult(resultResponse);
      setEvents(auditResponse.events);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught : (caught as ApiError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadCase();
    }, 0);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [actionPlanId]);

  const latestEvents = useMemo(() => events.slice(-5).reverse(), [events]);

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <header className="flex flex-col gap-4 border-b border-line pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-signal">案例详情</p>
          <h2 className="mt-1 break-all text-3xl font-semibold tracking-tight">
            {actionPlanId}
          </h2>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
            查看 Action Plan、审批、政策与事实依据、本地 Mock Result 和审计事件。此页面只读取业务事实，不执行工具。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            href="/cases"
            className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
          >
            返回案例列表
          </Link>
          <Link
            href={`/audit/${actionPlanId}`}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700"
          >
            查看完整审计时间线
          </Link>
        </div>
      </header>

      <SafeMockNotice />
      <ErrorNotice error={error} />

      {loading ? <EmptyState message="正在加载案例详情..." /> : null}

      {actionPlan ? (
        <>
          <Panel title="状态摘要" eyebrow="Action Plan">
            <div className="grid gap-3 md:grid-cols-5">
              <Metric label="状态" value={displayLabel(actionPlan.status)} raw={actionPlan.status} tone={toneForStatusValue(actionPlan.status)} />
              <Metric label="执行状态" value={displayLabel(actionPlan.execution_status)} raw={actionPlan.execution_status} tone={toneForStatusValue(actionPlan.execution_status)} />
              <Metric label="风险等级" value={displayLabel(actionPlan.risk_level)} raw={actionPlan.risk_level} tone={toneForRiskValue(actionPlan.risk_level)} />
              <Metric label="需要审批" value={yesNo(actionPlan.requires_approval)} tone={actionPlan.requires_approval ? "warning" : "success"} />
              <Metric label="Mock Result" value={result?.result_type ? displayLabel(result.result_type) : "尚未生成"} tone={result?.result_type ? "success" : "neutral"} />
            </div>
          </Panel>

          <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
            <Panel title="动作计划信息" eyebrow="基本信息">
              <dl className="grid gap-4 md:grid-cols-2">
                <KeyValue label="Action Plan ID" value={actionPlan.action_plan_id} />
                <KeyValue label="Run ID" value={actionPlan.run_id} />
                <KeyValue label="订单号" value={actionPlan.order_no ?? "无"} />
                <KeyValue label="意图" value={displayLabel(actionPlan.intent)} raw={actionPlan.intent} />
                <KeyValue label="计划工具" value={displayLabel(actionPlan.planned_tool_name)} raw={actionPlan.planned_tool_name} />
                <KeyValue label="动作类型" value={displayLabel(actionPlan.action_type)} raw={actionPlan.action_type} />
                <KeyValue label="金额" value={money(actionPlan.proposed_amount, actionPlan.currency)} />
                <KeyValue label="创建时间" value={formatDateTime(actionPlan.created_at)} />
              </dl>
              <div className="mt-5 rounded-lg border border-line bg-slate-50 p-4">
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  原始用户请求
                </div>
                <p className="mt-2 text-sm leading-6 text-slate-700">{actionPlan.request_message}</p>
              </div>
              <div className="mt-5 rounded-lg border border-line bg-slate-50 p-4">
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  处理摘要
                </div>
                <p className="mt-2 text-sm leading-6 text-slate-700">{actionPlan.summary}</p>
              </div>
            </Panel>

            <Panel title="审批摘要" eyebrow="Approval">
              {actionPlan.approval ? (
                <dl className="grid gap-4">
                  <KeyValue label="Approval ID" value={actionPlan.approval.approval_id} />
                  <KeyValue label="审批状态" value={displayLabel(actionPlan.approval.status)} raw={actionPlan.approval.status} />
                  <KeyValue label="请求动作" value={displayLabel(actionPlan.approval.requested_action_type)} raw={actionPlan.approval.requested_action_type} />
                  <KeyValue label="金额" value={money(actionPlan.approval.proposed_amount, actionPlan.approval.currency)} />
                  <KeyValue label="请求时间" value={formatDateTime(actionPlan.approval.requested_at)} />
                  <KeyValue label="决策时间" value={formatDateTime(actionPlan.approval.decided_at)} />
                  <Link
                    href="/approvals"
                    className="rounded-md bg-signal px-4 py-2 text-center text-sm font-semibold text-white hover:bg-teal-800"
                  >
                    前往审批中心
                  </Link>
                </dl>
              ) : (
                <EmptyState message="该 Action Plan 当前没有关联审批请求。" />
              )}
            </Panel>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <ListPanel title="处理原因" items={actionPlan.reasons} />
            <ListPanel title="下一步建议" items={actionPlan.next_steps} />
          </div>

          <Panel title="事实依据" eyebrow="Fact Evidence">
            <EvidenceGrid
              items={actionPlan.fact_evidence as Record<string, unknown>[]}
              empty="该 Action Plan 没有保存事实依据。"
            />
          </Panel>

          <Panel title="政策依据" eyebrow="Policy Evidence">
            <EvidenceGrid
              items={actionPlan.policy_evidence as Record<string, unknown>[]}
              empty="该 Action Plan 没有保存政策依据。"
            />
          </Panel>

          <Panel title="Mock Result" eyebrow="本地模拟记录">
            {result?.result ? (
              <div className="rounded-lg border border-line bg-slate-50 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="success">{displayLabel(result.result_type)}</Badge>
                  <Badge tone={toneForStatusValue(String(result.result.status))}>
                    {displayLabel(String(result.result.status))}
                  </Badge>
                </div>
                <dl className="mt-4 grid gap-3 md:grid-cols-2">
                  <KeyValue label={recordIdLabel(result.result_type)} value={recordId(result.result)} />
                  <KeyValue label="订单号" value={String(result.result.order_no)} />
                  <KeyValue label="工具" value={displayLabel(String(result.result.tool_name))} raw={String(result.result.tool_name)} />
                  <KeyValue label="创建时间" value={formatDateTime(String(result.result.created_at))} />
                </dl>
              </div>
            ) : (
              <EmptyState message="尚未生成本地模拟记录。审批通过后，可在工具执行页手动执行 Mock Tool。" />
            )}
          </Panel>

          <Panel
            title="审计预览"
            eyebrow="最近事件"
            action={
              <Link href={`/audit/${actionPlanId}`} className="text-sm font-semibold text-signal">
                查看完整时间线
              </Link>
            }
          >
            {latestEvents.length === 0 ? (
              <EmptyState message="当前没有审计事件。" />
            ) : (
              <AuditPreview events={latestEvents} />
            )}
          </Panel>

          <DebugJson title="Action Plan 调试 JSON" data={actionPlan} />
          <DebugJson title="Result 调试 JSON" data={result} />
        </>
      ) : null}
    </div>
  );
}

function Metric({
  label,
  value,
  raw,
  tone,
}: {
  label: string;
  value: string;
  raw?: string | null;
  tone?: "neutral" | "success" | "warning" | "danger" | "critical" | "info";
}) {
  return (
    <div className="rounded-lg border border-line bg-slate-50 p-3">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-2">
        <Badge tone={tone}>{value}</Badge>
      </div>
      {raw && raw !== value ? <div className="mt-1 text-xs text-slate-500">{raw}</div> : null}
    </div>
  );
}

function ListPanel({ title, items }: { title: string; items: string[] }) {
  return (
    <Panel title={title}>
      {items.length === 0 ? (
        <EmptyState message="暂无内容。" />
      ) : (
        <ul className="list-disc space-y-2 pl-5 text-sm text-slate-700">
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function EvidenceGrid({
  items,
  empty,
}: {
  items: Record<string, unknown>[];
  empty: string;
}) {
  if (items.length === 0) {
    return <EmptyState message={empty} />;
  }
  return (
    <div className="grid gap-3">
      {items.map((item, index) => (
        <div key={index} className="rounded-lg border border-line bg-slate-50 p-4">
          <dl className="grid gap-2 md:grid-cols-2">
            {Object.entries(item).map(([key, value]) => (
              <KeyValue key={key} label={key} value={stringValue(value)} />
            ))}
          </dl>
        </div>
      ))}
    </div>
  );
}

function AuditPreview({ events }: { events: AuditLogEvent[] }) {
  return (
    <ol className="space-y-3">
      {events.map((event) => (
        <li key={event.event_id} className="rounded-lg border border-line bg-slate-50 p-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={toneForStatusValue(event.event_type)}>{displayLabel(event.event_type)}</Badge>
            <span className="text-xs text-slate-500">{formatDateTime(event.created_at)}</span>
          </div>
          <div className="mt-2 text-sm text-slate-600">
            actor: {event.actor_type}
            {event.actor_id ? ` / ${event.actor_id}` : ""} · key: {event.idempotency_key ?? "无"}
          </div>
        </li>
      ))}
    </ol>
  );
}

function recordId(result: Record<string, unknown>): string {
  return String(result.refund_id ?? result.coupon_id ?? result.ticket_id ?? "无");
}

function stringValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "无";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}
