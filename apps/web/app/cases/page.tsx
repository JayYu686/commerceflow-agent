"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge } from "../../components/console/Badge";
import { EmptyState } from "../../components/console/EmptyState";
import { ErrorNotice } from "../../components/console/ErrorNotice";
import { KeyValue } from "../../components/console/KeyValue";
import { Panel } from "../../components/console/Panel";
import { SafeMockNotice } from "../../components/console/SafeMockNotice";
import { listActionPlans } from "../../lib/api";
import {
  displayLabel,
  formatDateTime,
  localizeText,
  money,
  toneForRiskValue,
  toneForStatusValue,
  yesNo,
} from "../../lib/display";
import type { ActionPlanListItem, ApiError } from "../../lib/types";

const statusOptions = ["", "planned", "pending_approval", "approved", "rejected", "not_executable"];
const executionOptions = ["", "not_executed", "not_applicable", "executed", "execution_failed"];

export default function CasesPage() {
  const [items, setItems] = useState<ActionPlanListItem[]>([]);
  const [status, setStatus] = useState("");
  const [executionStatus, setExecutionStatus] = useState("");
  const [orderNo, setOrderNo] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | Error | null>(null);

  async function loadCases() {
    setLoading(true);
    setError(null);
    try {
      const response = await listActionPlans({
        status: status || undefined,
        execution_status: executionStatus || undefined,
        order_no: orderNo.trim() || undefined,
        limit: 50,
      });
      setItems(response.action_plans);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught : (caught as ApiError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadCases();
    }, 0);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <header className="border-b border-line pb-6">
        <p className="text-sm font-semibold uppercase tracking-wide text-signal">Phase 5B</p>
        <h2 className="mt-1 text-3xl font-semibold tracking-tight">案例 / 动作计划列表</h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
          查找已经持久化的动作计划。进入案例详情后，可以查看审批状态、本地模拟结果和审计时间线。
        </p>
      </header>

      <SafeMockNotice />

      <Panel title="筛选条件" eyebrow="只读查询">
        <form
          className="grid gap-3 lg:grid-cols-[1fr_1fr_1fr_auto]"
          onSubmit={(event) => {
            event.preventDefault();
            void loadCases();
          }}
        >
          <label className="block text-sm">
            <span className="font-medium text-slate-700">动作计划状态</span>
            <select
              value={status}
              onChange={(event) => setStatus(event.target.value)}
              className="mt-2 w-full rounded-md border border-line bg-white px-3 py-2"
            >
              {statusOptions.map((option) => (
                <option key={option || "all"} value={option}>
                  {option ? displayLabel(option) : "全部状态"}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="font-medium text-slate-700">执行状态</span>
            <select
              value={executionStatus}
              onChange={(event) => setExecutionStatus(event.target.value)}
              className="mt-2 w-full rounded-md border border-line bg-white px-3 py-2"
            >
              {executionOptions.map((option) => (
                <option key={option || "all"} value={option}>
                  {option ? displayLabel(option) : "全部执行状态"}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="font-medium text-slate-700">订单号</span>
            <input
              value={orderNo}
              onChange={(event) => setOrderNo(event.target.value)}
              placeholder="例如 CF202605180023"
              className="mt-2 w-full rounded-md border border-line bg-white px-3 py-2"
            />
          </label>
          <div className="flex items-end">
            <button
              type="submit"
              className="rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700"
            >
              刷新列表
            </button>
          </div>
        </form>
      </Panel>

      <ErrorNotice error={error} />

      <Panel title="动作计划" eyebrow={loading ? "加载中" : `${items.length} 条记录`}>
        {loading ? (
          <EmptyState message="正在加载动作计划列表..." />
        ) : items.length === 0 ? (
          <EmptyState message="当前筛选条件下没有动作计划。可以先到 Agent 工作台创建一个动作计划。" />
        ) : (
          <div className="grid gap-3">
            {items.map((item) => (
              <Link
                key={item.action_plan_id}
                href={`/cases/${item.action_plan_id}`}
                className="rounded-lg border border-line bg-white p-4 hover:border-signal hover:bg-teal-50"
              >
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold text-ink">{item.action_plan_id}</span>
                      <Badge tone={toneForStatusValue(item.status)}>{displayLabel(item.status)}</Badge>
                      <Badge tone={toneForStatusValue(item.execution_status)}>
                        {displayLabel(item.execution_status)}
                      </Badge>
                      <Badge tone={toneForRiskValue(item.risk_level)}>
                        风险：{displayLabel(item.risk_level)}
                      </Badge>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-slate-600">
                      {localizeText(item.summary)}
                    </p>
                  </div>
                  <div className="grid gap-2 text-sm sm:grid-cols-2 lg:min-w-[360px]">
                    <KeyValue label="订单号" value={item.order_no ?? "无"} />
                    <KeyValue
                      label="计划工具"
                      value={displayLabel(item.planned_tool_name)}
                      raw={item.planned_tool_name}
                    />
                    <KeyValue label="金额" value={money(item.proposed_amount, item.currency)} />
                    <KeyValue label="需要审批" value={yesNo(item.requires_approval)} />
                    <KeyValue label="审批 ID" value={item.approval_id ?? "无"} />
                    <KeyValue label="创建时间" value={formatDateTime(item.created_at)} />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
