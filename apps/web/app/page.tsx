"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge } from "../components/console/Badge";
import { ErrorNotice } from "../components/console/ErrorNotice";
import { Panel } from "../components/console/Panel";
import { getHealth } from "../lib/api";
import { DEMO_SCENARIOS } from "../lib/demo-scenarios";
import type { ApiError, HealthResponse } from "../lib/types";

const capabilityChain = [
  "接收自然语言售后诉求",
  "确定性解析与受控 LLM 边界",
  "查询订单与物流事实",
  "检索售后政策依据",
  "生成处理建议与风险判断",
  "创建 Action Plan / 动作计划",
  "人工审批与审计记录",
  "受控 Mock 工具执行",
  "本地 stdio MCP 包装器",
];

const implemented = [
  "只读订单与物流查询 API",
  "基于确定性 embedding 的政策检索 API",
  "LangGraph 预览工作流",
  "受控 LLM adapter 边界",
  "Action Plan、审批与审计数据层",
  "Mock 退款、优惠券和工单工具 API",
  "本地 stdio MCP Server wrapper",
  "Phase 5A 浏览器总览与 Agent 工作台",
];

const notYetImplemented = [
  "浏览器审批批准 / 拒绝操作",
  "浏览器 Mock 工具执行操作",
  "案例级审计时间线详情页",
  "评测 Dashboard",
  "LangGraph interrupt / resume",
  "Agent 自动调用 MCP 工具",
  "真实支付、优惠券或客服系统",
];

export default function Home() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<ApiError | Error | null>(null);

  useEffect(() => {
    getHealth()
      .then((payload) => {
        setHealth(payload);
        setError(null);
      })
      .catch((caught: unknown) => {
        setHealth(null);
        setError(caught instanceof Error ? caught : (caught as ApiError));
      });
  }, []);

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <header className="flex flex-col gap-4 border-b border-line pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-signal">Phase 5A</p>
          <h2 className="mt-1 text-3xl font-semibold tracking-tight">
            CommerceFlow Agent 运营控制台
          </h2>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
            通过浏览器理解和测试受控售后 Agent：查看事实、政策依据、处理建议、风险等级、
            面向用户回复，并在明确幂等键保护下创建 Action Plan。
          </p>
        </div>
        <Link
          href="/workbench"
          className="inline-flex w-fit rounded-md bg-signal px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800"
        >
          进入 Agent 工作台
        </Link>
      </header>

      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <Panel title="系统状态" eyebrow="运行时">
          <div className="grid gap-3 sm:grid-cols-3">
            <Metric
              label="API 健康状态"
              value={health?.status ?? "未知"}
              tone={health?.status === "ok" ? "success" : "warning"}
            />
            <Metric label="环境" value={health?.environment ?? "未连接"} tone="info" />
            <Metric label="最近检查" value={health?.timestamp ?? "等待连接"} tone="neutral" />
          </div>
          <div className="mt-4">
            <ErrorNotice error={error} />
          </div>
        </Panel>

        <Panel title="安全边界" eyebrow="仅本地模拟">
          <div className="space-y-3 text-sm leading-6 text-slate-700">
            <p>
              控制台可以创建本地 Action Plan。后续 Phase 5B 页面才会提供审批和 Mock 工具执行入口。
              当前不会触发真实退款、真实赔付、真实发券或真实工单。
            </p>
            <div className="flex flex-wrap gap-2">
              <Badge tone="warning">仅预览，不执行</Badge>
              <Badge tone="danger">退款需要人工审批</Badge>
              <Badge tone="neutral">不调用真实外部系统</Badge>
            </div>
          </div>
        </Panel>
      </div>

      <Panel title="能力链路" eyebrow="已实现后端路径">
        <div className="grid gap-3 md:grid-cols-3">
          {capabilityChain.map((item, index) => (
            <div key={item} className="rounded-lg border border-line bg-slate-50 p-4">
              <div className="text-xs font-semibold text-slate-500">步骤 {index + 1}</div>
              <div className="mt-2 text-sm font-medium text-ink">{item}</div>
            </div>
          ))}
        </div>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="一键 Demo" eyebrow="工作台快捷入口">
          <div className="grid gap-3">
            {DEMO_SCENARIOS.map((scenario) => (
              <Link
                key={scenario.id}
                href={`/workbench?scenario=${scenario.id}`}
                className="rounded-lg border border-line bg-white p-4 text-left hover:border-signal hover:bg-teal-50"
              >
                <div className="text-sm font-semibold text-ink">{scenario.title}</div>
                <p className="mt-2 text-sm text-slate-600">{scenario.message}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {scenario.expected.slice(0, 3).map((item) => (
                    <Badge key={item} tone="info">
                      {item}
                    </Badge>
                  ))}
                </div>
              </Link>
            ))}
          </div>
        </Panel>

        <Panel title="已实现与后续范围" eyebrow="阶段边界">
          <div className="grid gap-5 md:grid-cols-2">
            <div>
              <h3 className="text-sm font-semibold text-emerald-800">已实现</h3>
              <ul className="mt-3 space-y-2 text-sm text-slate-700">
                {implemented.map((item) => (
                  <li key={item} className="border-l-4 border-emerald-400 pl-3">
                    {item}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-amber-800">Phase 5A 暂未实现</h3>
              <ul className="mt-3 space-y-2 text-sm text-slate-700">
                {notYetImplemented.map((item) => (
                  <li key={item} className="border-l-4 border-amber-400 pl-3">
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "neutral" | "success" | "warning" | "danger" | "critical" | "info";
}) {
  return (
    <div className="rounded-lg border border-line bg-slate-50 p-4">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-3">
        <Badge tone={tone}>{value}</Badge>
      </div>
    </div>
  );
}
