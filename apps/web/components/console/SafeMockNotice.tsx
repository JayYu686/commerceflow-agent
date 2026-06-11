import type { ReactNode } from "react";

export function SafeMockNotice({ children }: { children?: ReactNode }) {
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
      <div className="font-semibold">仅本地 Mock，不调用真实外部系统</div>
      <p className="mt-1">
        审批通过只代表允许后续执行本地 Mock Tool；工具执行只写入本地模拟记录、Action Plan 执行状态和审计日志。
        它不等于真实退款、真实赔付、真实发券或真实工单创建。
      </p>
      {children ? <div className="mt-2">{children}</div> : null}
    </div>
  );
}
