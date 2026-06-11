"use client";

import type { ApiError } from "../../lib/types";

type ErrorNoticeProps = {
  error: ApiError | Error | string | null;
};

const conflictMessages: Record<string, string> = {
  action_plan_already_executed: "该 Action Plan 已经执行，不能重复执行工具。",
  approval_already_decided: "该审批已经完成决策，不能重复批准或拒绝。",
  approval_mismatch: "请求中的审批记录与 Action Plan 不匹配。",
  approval_not_approved: "审批尚未批准，不能执行该工具。",
  approval_required: "该动作需要先完成人工审批。",
  amount_mismatch: "请求金额与 Action Plan 中的金额不一致。",
  currency_mismatch: "请求币种与 Action Plan 中的币种不一致。",
  duplicate_action_plan: "相同业务请求已存在 Action Plan。",
  duplicate_execution: "该 Action Plan 已经生成过 Mock Result。",
  idempotency_key_reused: "该幂等键已被不同请求使用。",
  missing_policy_evidence: "缺少可引用的政策依据，不能执行该工具。",
  order_mismatch: "请求订单号与 Action Plan 不一致。",
  tool_action_mismatch: "请求工具与 Action Plan 的 planned tool 不一致。",
};

export function ErrorNotice({ error }: ErrorNoticeProps) {
  if (!error) {
    return null;
  }

  const normalized = normalizeError(error);

  async function copyExistingIdentifier() {
    if (normalized.existingIdentifier && navigator.clipboard) {
      await navigator.clipboard.writeText(normalized.existingIdentifier);
    }
  }

  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
      <div className="font-semibold">请求未完成</div>
      <div className="mt-1">{normalized.message}</div>
      {normalized.detail ? <div className="mt-1 text-red-700">{normalized.detail}</div> : null}
      {normalized.existingIdentifier ? (
        <div className="mt-3 rounded-md border border-red-200 bg-white p-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-red-700">
            existing_identifier
          </div>
          <code className="mt-1 block break-all text-sm text-red-950">
            {normalized.existingIdentifier}
          </code>
          <button
            type="button"
            onClick={copyExistingIdentifier}
            className="mt-2 rounded-md border border-red-200 px-3 py-1.5 text-xs font-semibold text-red-800 hover:bg-red-100"
          >
            复制 existing_identifier
          </button>
        </div>
      ) : null}
    </div>
  );
}

function normalizeError(error: ApiError | Error | string): {
  message: string;
  detail?: string;
  existingIdentifier?: string | null;
} {
  if (typeof error === "string") {
    return { message: error };
  }

  if (!("status" in error)) {
    return { message: error.message || "服务暂时不可用，请查看后端日志。" };
  }

  const existingIdentifier = error.existing_identifier ?? null;

  if (error.status === 422) {
    return {
      message: "请求参数不完整或格式不正确。",
      detail: error.message,
      existingIdentifier,
    };
  }

  if (error.status === 404) {
    return { message: "资源不存在。", detail: error.message, existingIdentifier };
  }

  if (error.status === 409) {
    return {
      message: conflictMessages[error.code] ?? "请求被后端安全规则拦截。",
      detail:
        error.code === "duplicate_action_plan"
          ? "这是业务防重复保护，不是系统错误。请复用现有 Action Plan，或修改请求后刷新幂等键。"
          : error.message,
      existingIdentifier,
    };
  }

  if (error.status >= 500) {
    return {
      message: "服务暂时不可用，请查看后端日志。",
      detail: error.message,
      existingIdentifier,
    };
  }

  return {
    message: error.message || `请求失败（HTTP ${error.status}）。`,
    detail: error.code,
    existingIdentifier,
  };
}
