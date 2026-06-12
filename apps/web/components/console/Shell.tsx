import Link from "next/link";
import type { ReactNode } from "react";

import { Badge } from "./Badge";

const navigation = [
  { label: "总览", href: "/", phase: "5A" },
  { label: "Agent 工作台", href: "/workbench", phase: "5A" },
  { label: "案例", href: "/cases", phase: "5B" },
  { label: "审批中心", href: "/approvals", phase: "5B" },
  { label: "工具执行", href: "/tools", phase: "5B" },
  { label: "审计", href: "/audit", phase: "5B" },
  { label: "评测", href: "/evaluation", phase: "5C" },
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
            {navigation.map((item) => (
              <Link
                key={item.label}
                href={item.href}
                className="flex items-center justify-between rounded-md px-3 py-2 font-medium text-slate-700 hover:bg-slate-100"
              >
                <span>{item.label}</span>
                <span className="text-xs text-slate-400">{item.phase}</span>
              </Link>
            ))}
          </nav>
          <div className="mt-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-900">
            <div className="font-semibold">安全边界</div>
            <p className="mt-1 leading-6">
              本演示中的退款、优惠券和工单均为本地模拟记录，不会调用真实支付、优惠券、客服或物流系统。
              Agent 不会自动审批，也不会自动调用 MCP 或工具。
            </p>
          </div>
        </aside>
        <main className="min-w-0 px-5 py-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
