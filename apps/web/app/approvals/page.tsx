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
import { decideApproval, getApproval, listApprovals } from "../../lib/api";
import {
  displayLabel,
  formatDateTime,
  money,
  toneForRiskValue,
  toneForStatusValue,
} from "../../lib/display";
import { newIdempotencyKey } from "../../lib/idempotency";
import type { ApiError, ApprovalRequestResponse } from "../../lib/types";

type ApprovalStatus = "pending" | "approved" | "rejected";

const tabs: { status: ApprovalStatus; label: string }[] = [
  { status: "pending", label: "待审批" },
  { status: "approved", label: "已批准" },
  { status: "rejected", label: "已拒绝" },
];

export default function ApprovalsPage() {
  const [activeStatus, setActiveStatus] = useState<ApprovalStatus>("pending");
  const [approvals, setApprovals] = useState<ApprovalRequestResponse[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selected, setSelected] = useState<ApprovalRequestResponse | null>(null);
  const [reviewer, setReviewer] = useState("demo_reviewer");
  const [comment, setComment] = useState("证据与政策匹配，同意进入后续本地模拟工具执行。");
  const [idempotencyKey, setIdempotencyKey] = useState("");
  const [loading, setLoading] = useState(true);
  const [deciding, setDeciding] = useState(false);
  const [error, setError] = useState<ApiError | Error | null>(null);

  async function loadApprovals(status = activeStatus) {
    setLoading(true);
    setError(null);
    try {
      const response = await listApprovals(status, 50);
      setApprovals(response.approvals);
      const nextSelectedId = response.approvals[0]?.approval_id ?? null;
      setSelectedId(nextSelectedId);
      setSelected(nextSelectedId ? await getApproval(nextSelectedId) : null);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught : (caught as ApiError));
    } finally {
      setLoading(false);
    }
  }

  async function loadSelected(approvalId: string) {
    setError(null);
    setSelectedId(approvalId);
    try {
      setSelected(await getApproval(approvalId));
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught : (caught as ApiError));
    }
  }

  async function submitDecision(decision: "approve" | "reject") {
    if (!selected || !idempotencyKey) {
      return;
    }
    setDeciding(true);
    setError(null);
    try {
      const response = await decideApproval(
        selected.approval_id,
        {
          decision,
          reviewer,
          comment: comment.trim() || null,
        },
        idempotencyKey,
      );
      setSelected(response);
      const refreshed = await listApprovals(activeStatus, 50);
      setApprovals(refreshed.approvals);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught : (caught as ApiError));
    } finally {
      setDeciding(false);
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setIdempotencyKey(newIdempotencyKey("web-approval-decision"));
      void loadApprovals("pending");
    }, 0);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const policyIds = useMemo(() => selected?.policy_ids ?? [], [selected]);

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <header className="border-b border-line pb-6">
        <p className="text-sm font-semibold uppercase tracking-wide text-signal">Phase 5B</p>
        <h2 className="mt-1 text-3xl font-semibold tracking-tight">审批中心</h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
          审批高风险退款或高额补偿动作。批准只代表允许后续执行本地模拟工具，不代表已经真实退款、真实赔付或真实发券。
        </p>
      </header>

      <SafeMockNotice />
      <ErrorNotice error={error} />

      <div className="grid gap-6 xl:grid-cols-[420px_1fr]">
        <Panel title="审批列表" eyebrow={loading ? "加载中" : `${approvals.length} 条`}>
          <div className="mb-4 flex flex-wrap gap-2">
            {tabs.map((tab) => (
              <button
                key={tab.status}
                type="button"
                onClick={() => {
                  setActiveStatus(tab.status);
                  void loadApprovals(tab.status);
                }}
                className={`rounded-md px-3 py-2 text-sm font-semibold ${
                  activeStatus === tab.status
                    ? "bg-slate-900 text-white"
                    : "border border-line bg-white text-slate-700 hover:bg-slate-100"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {loading ? (
            <EmptyState message="正在加载审批列表..." />
          ) : approvals.length === 0 ? (
            <EmptyState message="当前状态下没有审批请求。" />
          ) : (
            <div className="grid gap-3">
              {approvals.map((approval) => (
                <button
                  key={approval.approval_id}
                  type="button"
                  onClick={() => void loadSelected(approval.approval_id)}
                  className={`rounded-lg border p-4 text-left ${
                    approval.approval_id === selectedId
                      ? "border-signal bg-teal-50"
                      : "border-line bg-white hover:border-signal"
                  }`}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={toneForStatusValue(approval.status)}>
                      {displayLabel(approval.status)}
                    </Badge>
                    <Badge tone={toneForRiskValue(approval.risk_level)}>
                      {displayLabel(approval.risk_level)}
                    </Badge>
                  </div>
                  <div className="mt-2 break-all text-sm font-semibold">{approval.approval_id}</div>
                  <div className="mt-1 text-sm text-slate-600">
                    {approval.action_plan.order_no ?? "无订单"} ·{" "}
                    {displayLabel(approval.requested_action_type)} ·{" "}
                    {money(approval.proposed_amount, approval.currency)}
                  </div>
                </button>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="审批详情" eyebrow="人工决策">
          {!selected ? (
            <EmptyState message="请选择一个审批请求。" />
          ) : (
            <div className="space-y-5">
              <div className="grid gap-4 md:grid-cols-2">
                <KeyValue label="审批 ID" value={selected.approval_id} />
                <KeyValue label="动作计划 ID" value={selected.action_plan_id} />
                <KeyValue label="状态" value={displayLabel(selected.status)} raw={selected.status} />
                <KeyValue
                  label="请求动作"
                  value={displayLabel(selected.requested_action_type)}
                  raw={selected.requested_action_type}
                />
                <KeyValue label="订单号" value={selected.action_plan.order_no ?? "无"} />
                <KeyValue label="金额" value={money(selected.proposed_amount, selected.currency)} />
                <KeyValue label="申请人" value={selected.requester} />
                <KeyValue label="请求时间" value={formatDateTime(selected.requested_at)} />
                <KeyValue label="审核人" value={selected.reviewer ?? "未决策"} />
                <KeyValue label="决策时间" value={formatDateTime(selected.decided_at)} />
              </div>

              <div className="rounded-lg border border-line bg-slate-50 p-4">
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  政策依据
                </div>
                {policyIds.length === 0 ? (
                  <p className="mt-2 text-sm text-slate-500">没有保存政策 ID。</p>
                ) : (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {policyIds.map((policyId) => (
                      <Badge key={policyId} tone="info">
                        {policyId}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>

              <div className="rounded-lg border border-line bg-slate-50 p-4">
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  决策说明
                </div>
                <p className="mt-2 text-sm text-slate-700">
                  {selected.decision_comment ?? "尚未填写决策说明。"}
                </p>
              </div>

              {selected.status === "pending" ? (
                <form
                  className="space-y-4"
                  onSubmit={(event) => {
                    event.preventDefault();
                  }}
                >
                  <IdempotencyKeyBox value={idempotencyKey} onRefresh={() => setIdempotencyKey(newIdempotencyKey("web-approval-decision"))} />
                  <label className="block text-sm">
                    <span className="font-medium text-slate-700">审核人</span>
                    <input
                      value={reviewer}
                      onChange={(event) => setReviewer(event.target.value)}
                      className="mt-2 w-full rounded-md border border-line bg-white px-3 py-2"
                    />
                  </label>
                  <label className="block text-sm">
                    <span className="font-medium text-slate-700">审批意见</span>
                    <textarea
                      value={comment}
                      onChange={(event) => setComment(event.target.value)}
                      rows={4}
                      className="mt-2 w-full rounded-md border border-line bg-white px-3 py-2"
                    />
                  </label>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={deciding || !idempotencyKey || !reviewer.trim()}
                      onClick={() => void submitDecision("approve")}
                      className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:bg-slate-300"
                    >
                      批准
                    </button>
                    <button
                      type="button"
                      disabled={deciding || !idempotencyKey || !reviewer.trim()}
                      onClick={() => void submitDecision("reject")}
                      className="rounded-md bg-red-700 px-4 py-2 text-sm font-semibold text-white hover:bg-red-800 disabled:cursor-not-allowed disabled:bg-slate-300"
                    >
                      拒绝
                    </button>
                  </div>
                </form>
              ) : (
                <div className="rounded-lg border border-line bg-slate-50 p-4 text-sm text-slate-700">
                  该审批已经决策。审批通过不等于已退款；如需执行本地模拟工具，请前往工具执行页。
                </div>
              )}

              <div className="flex flex-wrap gap-2">
                <Link
                  href={`/cases/${selected.action_plan_id}`}
                  className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
                >
                  查看案例详情
                </Link>
                <Link
                  href="/tools"
                  className="rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700"
                >
                  前往工具执行
                </Link>
              </div>

              <DebugJson title="审批调试 JSON" data={selected} />
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}
