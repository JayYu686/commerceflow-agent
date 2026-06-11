"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge } from "../components/console/Badge";
import { ErrorNotice } from "../components/console/ErrorNotice";
import { Panel } from "../components/console/Panel";
import { SafeMockNotice } from "../components/console/SafeMockNotice";
import { getHealth } from "../lib/api";
import { DEMO_SCENARIOS } from "../lib/demo-scenarios";
import type { ApiError, HealthResponse } from "../lib/types";

const capabilityChain = [
  "接收自然语言售后诉求",
  "确定性解析与受控 LLM 辅助理解",
  "查询订单与物流事实",
  "检索售后政策依据",
  "生成处理建议与风险等级",
  "创建 Action Plan / 动作计划",
  "人工审批 approve / reject",
  "人工触发本地 Mock 工具执行",
  "查看 Mock Result 与审计时间线",
];

const implemented = [
  "只读订单与物流查询 API",
  "政策 RAG 检索 API",
  "LangGraph Agent Preview 工作流",
  "OpenAI-compatible 受控 LLM Provider",
  "Action Plan、审批与审计数据层",
  "Mock 退款、优惠券和工单工具 API",
  "本地 stdio MCP Server wrapper",
  "中文 Agent 工作台",
  "审批中心、工具执行和审计时间线 UI",
];

const notYetImplemented = [
  "LangGraph interrupt / resume",
  "Agent 自动调用 MCP 工具",
  "真实支付、优惠券、客服或物流系统",
  "真实 Evaluation Dashboard 和评测报告",
  "生产级认证、权限和多租户",
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
          <p className="text-sm font-semibold uppercase tracking-wide text-signal">Phase 5B</p>
          <h2 className="mt-1 text-3xl font-semibold tracking-tight">
            CommerceFlow Agent 运营控制台
          </h2>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
            通过浏览器完成从 Agent 预览、创建 Action Plan、人工审批、Mock 工具执行到审计复盘的完整演示链路。
            所有执行结果都是本地模拟记录，不调用真实外部业务系统。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            href="/workbench"
            className="rounded-md bg-signal px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800"
          >
            进入 Agent 工作台
          </Link>
          <Link
            href="/cases"
            className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
          >
            查看案例
          </Link>
        </div>
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

        <SafeMockNotice />
      </div>

      <Panel title="能力链路" eyebrow="浏览器可演示">
        <div className="grid gap-3 md:grid-cols-3">
          {capabilityChain.map((item, index) => (
            <div key={item} className="rounded-lg border border-line bg-slate-50 p-4">
              <div className="text-xs font-semibold text-slate-500">步骤 {index + 1}</div>
              <div className="mt-2 text-sm font-medium text-ink">{item}</div>
            </div>
          ))}
        </div>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title="一键 Demo" eyebrow="工作台入口">
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

        <Panel title="已实现模块" eyebrow="当前可演示">
          <ul className="space-y-2 text-sm text-slate-700">
            {implemented.map((item) => (
              <li key={item} className="border-l-4 border-emerald-400 pl-3">
                {item}
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title="尚未实现" eyebrow="后续阶段">
          <ul className="space-y-2 text-sm text-slate-700">
            {notYetImplemented.map((item) => (
              <li key={item} className="border-l-4 border-amber-400 pl-3">
                {item}
              </li>
            ))}
          </ul>
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
