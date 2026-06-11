import Link from "next/link";

import { Panel } from "../../components/console/Panel";
import { SafeMockNotice } from "../../components/console/SafeMockNotice";

export default function AuditIndexPage() {
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header className="border-b border-line pb-6">
        <p className="text-sm font-semibold uppercase tracking-wide text-signal">Phase 5B</p>
        <h2 className="mt-1 text-3xl font-semibold tracking-tight">审计时间线</h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
          审计时间线按 Action Plan 展示。请先从案例列表选择一个案例，再进入对应审计详情。
        </p>
      </header>
      <SafeMockNotice />
      <Panel title="选择案例" eyebrow="只读审计">
        <Link
          href="/cases"
          className="inline-flex rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700"
        >
          前往案例列表
        </Link>
      </Panel>
    </div>
  );
}
