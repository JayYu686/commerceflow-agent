import Link from "next/link";
import type { ReactNode } from "react";

import { Badge } from "./Badge";

const navigation = [
  { label: "总览", href: "/", phase: "5A" },
  { label: "Agent 工作台", href: "/workbench", phase: "5A" },
  { label: "案例", href: null, phase: "5B" },
  { label: "审批中心", href: null, phase: "5B" },
  { label: "工具执行", href: null, phase: "5B" },
  { label: "审计", href: null, phase: "5B" },
  { label: "评测", href: null, phase: "5C" },
];

export function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-panel text-ink">
      <div className="grid min-h-screen lg:grid-cols-[280px_1fr]">
        <aside className="border-b border-line bg-white px-5 py-5 lg:border-b-0 lg:border-r">
          <div className="flex items-start justify-between gap-3 lg:block">
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-signal">
                CommerceFlow
              </div>
              <h1 className="mt-1 text-2xl font-semibold">Agent 控制台</h1>
            </div>
            <Badge tone="warning">仅本地模拟</Badge>
          </div>
          <nav className="mt-6 grid gap-2 text-sm">
            {navigation.map((item) =>
              item.href ? (
                <Link
                  key={item.label}
                  href={item.href}
                  className="flex items-center justify-between rounded-md px-3 py-2 font-medium text-slate-700 hover:bg-slate-100"
                >
                  <span>{item.label}</span>
                  <span className="text-xs text-slate-400">{item.phase}</span>
                </Link>
              ) : (
                <div
                  key={item.label}
                  className="flex items-center justify-between rounded-md px-3 py-2 text-slate-400"
                >
                  <span>{item.label}</span>
                  <span className="rounded border border-slate-200 px-1.5 py-0.5 text-xs">
                    {item.phase} 即将推出
                  </span>
                </div>
              ),
            )}
          </nav>
          <div className="mt-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-900">
            <div className="font-semibold">安全边界</div>
            <p className="mt-1">
              本演示中的退款、优惠券和工单均为本地 Mock 记录，不会调用真实支付、
              优惠券、客服或物流系统。
            </p>
          </div>
        </aside>
        <main className="min-w-0 px-5 py-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
