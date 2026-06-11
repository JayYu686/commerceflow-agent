"use client";

import type { ApiError } from "../../lib/types";

type ErrorNoticeProps = {
  error: ApiError | Error | string | null;
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
      <div className="font-semibold">请求失败</div>
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
    return { message: error.message || "服务暂时不可用，请查看后端日志" };
  }

  const existingIdentifier = error.existing_identifier ?? null;

  if (error.status === 422) {
    return {
      message: "请求参数不完整或格式不正确",
      detail: error.message,
      existingIdentifier,
    };
  }

  if (error.status === 404) {
    return { message: "资源不存在", detail: error.message, existingIdentifier };
  }

  if (error.status === 409 && error.code === "duplicate_action_plan") {
    return {
      message: "相同业务请求已存在 Action Plan",
      detail: "这是业务防重复保护，不是系统错误。请复用现有 Action Plan，或修改请求内容后刷新幂等键。",
      existingIdentifier,
    };
  }

  if (error.status === 409 && error.code === "idempotency_key_reused") {
    return {
      message: "该幂等键已被不同请求使用",
      detail: "请刷新幂等键后再提交新的 Action Plan 创建请求。",
      existingIdentifier,
    };
  }

  if (error.status >= 500) {
    return {
      message: "服务暂时不可用，请查看后端日志",
      detail: error.message,
      existingIdentifier,
    };
  }

  return {
    message: error.message || `请求失败（HTTP ${error.status}）`,
    detail: error.code,
    existingIdentifier,
  };
}
