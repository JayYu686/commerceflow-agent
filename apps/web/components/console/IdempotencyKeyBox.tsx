"use client";

type IdempotencyKeyBoxProps = {
  value: string;
  onRefresh: () => void;
};

export function IdempotencyKeyBox({ value, onRefresh }: IdempotencyKeyBoxProps) {
  const hasValue = value.trim().length > 0;

  async function copyKey() {
    if (hasValue && navigator.clipboard) {
      await navigator.clipboard.writeText(value);
    }
  }

  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-amber-800">
            幂等键 Idempotency-Key
          </div>
          <code className="mt-1 block break-all text-sm text-amber-950">
            {hasValue ? value : "正在生成幂等键..."}
          </code>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={copyKey}
            disabled={!hasValue}
            className="rounded-md border border-amber-300 bg-white px-3 py-2 text-sm font-medium text-amber-900 hover:bg-amber-100 disabled:cursor-not-allowed disabled:border-amber-100 disabled:text-amber-300"
          >
            复制
          </button>
          <button
            type="button"
            onClick={onRefresh}
            className="rounded-md bg-amber-700 px-3 py-2 text-sm font-medium text-white hover:bg-amber-800"
          >
            刷新幂等键
          </button>
        </div>
      </div>
      <p className="mt-3 text-xs text-amber-900">
        使用相同幂等键重试应返回同一个 Action Plan。只有要发起新的创建尝试时才刷新幂等键。
      </p>
    </div>
  );
}
