"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Badge } from "../../../components/console/Badge";
import { DebugJson } from "../../../components/console/DebugJson";
import { EmptyState } from "../../../components/console/EmptyState";
import { ErrorNotice } from "../../../components/console/ErrorNotice";
import { KeyValue } from "../../../components/console/KeyValue";
import { Panel } from "../../../components/console/Panel";
import { SafeMockNotice } from "../../../components/console/SafeMockNotice";
import { getActionPlan, getActionPlanAuditLogs } from "../../../lib/api";
import {
  actorLabel,
  displayLabel,
  formatDateTime,
  payloadKeyLabel,
  payloadValueLabel,
  toneForStatusValue,
} from "../../../lib/display";
import type { ActionPlanResponse, ApiError, AuditLogEvent } from "../../../lib/types";

export default function AuditTimelinePage() {
  const params = useParams<{ actionPlanId: string }>();
  const actionPlanId = Array.isArray(params.actionPlanId)
    ? params.actionPlanId[0]
    : params.actionPlanId;
  const [actionPlan, setActionPlan] = useState<ActionPlanResponse | null>(null);
  const [events, setEvents] = useState<AuditLogEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | Error | null>(null);

  async function loadAudit() {
    if (!actionPlanId) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [planResponse, auditResponse] = await Promise.all([
        getActionPlan(actionPlanId),
        getActionPlanAuditLogs(actionPlanId),
      ]);
      setActionPlan(planResponse);
      setEvents(auditResponse.events);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught : (caught as ApiError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadAudit();
    }, 0);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [actionPlanId]);

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <header className="flex flex-col gap-4 border-b border-line pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-signal">审计时间线</p>
          <h2 className="mt-1 break-all text-3xl font-semibold tracking-tight">{actionPlanId}</h2>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
            只读展示动作计划、审批和本地模拟工具执行相关事件。审计日志不提供修改或删除入口。
          </p>
        </div>
        <Link
          href={`/cases/${actionPlanId}`}
          className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
        >
          返回案例详情
        </Link>
      </header>

      <SafeMockNotice />
      <ErrorNotice error={error} />

      {actionPlan ? (
        <Panel title="动作计划摘要" eyebrow="审计对象">
          <div className="grid gap-3 md:grid-cols-4">
            <KeyValue label="订单号" value={actionPlan.order_no ?? "无"} />
            <KeyValue label="动作" value={displayLabel(actionPlan.action_type)} raw={actionPlan.action_type} />
            <KeyValue label="状态" value={displayLabel(actionPlan.status)} raw={actionPlan.status} />
            <KeyValue
              label="执行状态"
              value={displayLabel(actionPlan.execution_status)}
              raw={actionPlan.execution_status}
            />
          </div>
        </Panel>
      ) : null}

      <Panel title="事件时间线" eyebrow={loading ? "加载中" : `${events.length} 条事件`}>
        {loading ? (
          <EmptyState message="正在加载审计事件..." />
        ) : events.length === 0 ? (
          <EmptyState message="当前动作计划没有审计事件。" />
        ) : (
          <ol className="space-y-4">
            {events.map((event, index) => (
              <li key={event.event_id} className="flex gap-3">
                <div className="flex flex-col items-center">
                  <div className="grid h-8 w-8 place-items-center rounded-full bg-slate-900 text-xs font-semibold text-white">
                    {index + 1}
                  </div>
                  {index < events.length - 1 ? <div className="h-full w-px bg-line" /> : null}
                </div>
                <div className="min-w-0 flex-1 rounded-lg border border-line bg-white p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={toneForStatusValue(event.event_type)}>
                      {displayLabel(event.event_type)}
                    </Badge>
                    <span className="text-xs text-slate-500">{formatDateTime(event.created_at)}</span>
                  </div>
                  <dl className="mt-4 grid gap-3 md:grid-cols-3">
                    <KeyValue label="事件 ID" value={event.event_id} />
                    <KeyValue label="操作者" value={actorLabel(event.actor_type, event.actor_id)} />
                    <KeyValue label="幂等键" value={event.idempotency_key ?? "无"} />
                    <KeyValue label="订单号" value={event.order_no ?? "无"} />
                    <KeyValue label="审批 ID" value={event.approval_id ?? "无"} />
                    <KeyValue label="动作计划 ID" value={event.action_plan_id ?? "无"} />
                  </dl>
                  <PayloadTable payload={event.payload} />
                  <div className="mt-4">
                    <DebugJson title="事件调试 JSON" data={event} />
                  </div>
                </div>
              </li>
            ))}
          </ol>
        )}
      </Panel>
    </div>
  );
}

function PayloadTable({ payload }: { payload: Record<string, unknown> }) {
  const entries = Object.entries(payload);
  if (entries.length === 0) {
    return <EmptyState message="该事件没有 payload。" />;
  }
  return (
    <div className="mt-4 rounded-lg border border-line bg-slate-50 p-3">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        安全筛选后的事件载荷
      </div>
      <dl className="mt-3 grid gap-2 md:grid-cols-2">
        {entries.map(([key, value]) => (
          <KeyValue key={key} label={payloadKeyLabel(key)} value={payloadValueLabel(key, value)} />
        ))}
      </dl>
    </div>
  );
}
