"use client";

import { useEffect, useMemo, useState } from "react";

import { Badge } from "../../components/console/Badge";
import { DebugJson } from "../../components/console/DebugJson";
import { ErrorNotice } from "../../components/console/ErrorNotice";
import { Panel } from "../../components/console/Panel";
import { getLatestEvaluationReport, listEvaluationReports } from "../../lib/api";
import { displayLabel, formatDateTime, toneForStatusValue } from "../../lib/display";
import type { ApiError, EvaluationCaseResult, EvaluationMetric, EvaluationReport } from "../../lib/types";

const primaryMetricKeys = [
  "task_success_rate",
  "policy_recall_at_k",
  "unsafe_action_block_rate",
  "approval_enforcement_rate",
  "idempotency_protection_rate",
];

const safetyMetricKeys = [
  "unsafe_action_block_rate",
  "approval_enforcement_rate",
  "idempotency_protection_rate",
  "tool_argument_accuracy",
  "protected_tables_unchanged",
  "order_status_unchanged",
  "trace_completeness",
];

const evaluationCommand = [
  "Set-Location services/api",
  "..\\..\\.venv\\Scripts\\python.exe -m scripts.run_evaluation `",
  "  --dataset ..\\..\\data\\eval\\mvp_eval_v1.jsonl `",
  "  --output ..\\..\\eval\\reports\\mvp_run_deterministic.json `",
  "  --markdown ..\\..\\eval\\reports\\MVP_REPORT.md `",
  "  --provider disabled",
].join("\n");

export default function EvaluationPage() {
  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [reportCount, setReportCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | Error | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadReport() {
      setLoading(true);
      setError(null);
      try {
        const reports = await listEvaluationReports();
        if (!cancelled) {
          setReportCount(reports.reports.length);
        }

        try {
          const latest = await getLatestEvaluationReport();
          if (!cancelled) {
            setReport(latest);
          }
        } catch (latestError) {
          if (isApiError(latestError) && latestError.status === 404) {
            if (!cancelled) {
              setReport(null);
            }
          } else {
            throw latestError;
          }
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError : (loadError as ApiError));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadReport();
    return () => {
      cancelled = true;
    };
  }, []);

  const failedCases = useMemo(
    () => report?.cases.filter((item) => !item.success).slice(0, 20) ?? [],
    [report],
  );

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header className="border-b border-line pb-6">
        <p className="text-sm font-semibold uppercase tracking-wide text-signal">Phase 5C</p>
        <h2 className="mt-1 text-3xl font-semibold tracking-tight">评测看板</h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
          本页只展示已经保存的评测报告。没有运行评测时不会显示任何假指标；真实 DeepSeek
          指标也必须先通过评测命令生成报告后才会出现在这里。
        </p>
      </header>

      <ErrorNotice error={error} />

      {loading ? (
        <Panel title="正在读取评测报告" eyebrow="Evaluation reports">
          <p className="text-sm text-slate-600">正在从后端读取 eval/reports 下的保存报告...</p>
        </Panel>
      ) : null}

      {!loading && !report ? <EmptyEvaluationState reportCount={reportCount} /> : null}

      {report ? (
        <>
          <section className="grid gap-4 md:grid-cols-5">
            {primaryMetricKeys.map((key) => (
              <MetricCard key={key} name={key} metric={report.metrics[key]} />
            ))}
          </section>

          <section className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
            <Panel title="评测环境" eyebrow="Run metadata">
              <dl className="grid gap-3 text-sm">
                <MetaRow label="报告 ID" value={report.report_id} />
                <MetaRow label="Git Commit" value={report.environment.git_commit} />
                <MetaRow label="数据集" value={report.environment.dataset_version} />
                <MetaRow label="Seed 版本" value={report.environment.seed_data_version} />
                <MetaRow label="LLM Provider" value={displayLabel(report.environment.model_provider)} />
                <MetaRow label="Embedding" value={report.environment.embedding_provider} />
                <MetaRow label="运行时间" value={formatDateTime(report.environment.run_date)} />
              </dl>
            </Panel>

            <Panel title="总体结果" eyebrow="Summary">
              <div className="grid gap-4 sm:grid-cols-3">
                <SummaryNumber label="总案例数" value={String(report.summary.total_cases)} />
                <SummaryNumber label="通过案例" value={String(report.summary.passed_cases)} tone="success" />
                <SummaryNumber label="失败案例" value={String(report.summary.failed_cases)} tone="danger" />
              </div>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <SummaryNumber label="平均延迟" value={`${report.summary.average_latency_ms} ms`} />
                <SummaryNumber label="P95 延迟" value={`${report.summary.p95_latency_ms} ms`} />
              </div>
              <p className="mt-4 text-xs leading-5 text-slate-500">
                当前基线为确定性评测，不调用真实外部模型；Mock 工具只写本地模拟记录和审计日志。
              </p>
            </Panel>
          </section>

          <Panel title="分类结果" eyebrow="Breakdown">
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="border-b border-line text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="py-2 pr-4">类别</th>
                    <th className="py-2 pr-4">案例数</th>
                    <th className="py-2 pr-4">通过</th>
                    <th className="py-2 pr-4">成功率</th>
                    <th className="py-2 pr-4">主要失败原因</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {report.breakdown.map((item) => (
                    <tr key={item.category}>
                      <td className="py-3 pr-4 font-medium text-ink">{displayLabel(item.category)}</td>
                      <td className="py-3 pr-4">{item.count}</td>
                      <td className="py-3 pr-4">{item.successes}</td>
                      <td className="py-3 pr-4">
                        <Badge tone={item.task_success_rate === 1 ? "success" : "warning"}>
                          {formatPercent(item.task_success_rate)}
                        </Badge>
                      </td>
                      <td className="py-3 pr-4 text-slate-600">
                        {item.main_failure ? displayLabel(item.main_failure) : "无"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>

          <Panel title="安全指标" eyebrow="Safety">
            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
              {safetyMetricKeys.map((key) => (
                <MetricCard key={key} name={key} metric={report.metrics[key]} compact />
              ))}
            </div>
            <p className="mt-4 text-sm leading-6 text-slate-600">
              安全评测覆盖越权请求拦截、审批约束、幂等保护、工具参数校验、受保护业务表不变和审计轨迹完整性。
            </p>
          </Panel>

          <Panel title="失败案例" eyebrow="Representative failures">
            {failedCases.length ? (
              <div className="overflow-x-auto">
                <table className="min-w-full text-left text-sm">
                  <thead className="border-b border-line text-xs uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="py-2 pr-4">Case ID</th>
                      <th className="py-2 pr-4">类别</th>
                      <th className="py-2 pr-4">失败原因</th>
                      <th className="py-2 pr-4">实际结果</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {failedCases.map((item) => (
                      <CaseResultRow key={item.case_id} item={item} />
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-slate-600">本次报告没有失败案例。</p>
            )}
          </Panel>

          <Panel title="代表性成功 Trace" eyebrow="Representative successes">
            <div className="grid gap-3 lg:grid-cols-2">
              {report.representative_successes.slice(0, 4).map((item) => (
                <TraceCard key={item.case_id} item={item} />
              ))}
            </div>
          </Panel>

          <Panel title="限制说明" eyebrow="Limitations">
            <ul className="list-disc space-y-2 pl-5 text-sm leading-6 text-slate-600">
              {report.limitations.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </Panel>

          <DebugJson title="调试 JSON" data={report} />
        </>
      ) : null}
    </div>
  );
}

function EmptyEvaluationState({ reportCount }: { reportCount: number }) {
  return (
    <Panel title="尚未运行评测" eyebrow="No saved report">
      <div className="space-y-4">
        <p className="text-sm leading-6 text-slate-600">
          后端当前没有可展示的评测报告。请先在本地执行确定性评测命令，生成 JSON 和 Markdown
          报告后再刷新本页面。
        </p>
        <pre className="overflow-auto rounded-md bg-slate-950 p-4 text-xs leading-5 text-slate-100">
          {evaluationCommand}
        </pre>
        <div className="flex flex-wrap gap-2">
          <Badge tone="info">已发现报告数：{reportCount}</Badge>
          <Badge tone="warning">不展示假指标</Badge>
          <Badge tone="info">默认 provider=disabled</Badge>
        </div>
      </div>
    </Panel>
  );
}

function MetricCard({
  name,
  metric,
  compact = false,
}: {
  name: string;
  metric?: EvaluationMetric;
  compact?: boolean;
}) {
  const value = metric ? formatPercent(metric.value) : "未覆盖";
  const tone = !metric ? "neutral" : metric.value === 1 ? "success" : metric.value && metric.value >= 0.8 ? "warning" : "danger";
  return (
    <div className="rounded-lg border border-line bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{displayLabel(name)}</p>
          <p className={compact ? "mt-2 text-2xl font-semibold text-ink" : "mt-3 text-3xl font-semibold text-ink"}>
            {value}
          </p>
        </div>
        <Badge tone={tone}>{metric ? `${metric.passed}/${metric.total}` : "0/0"}</Badge>
      </div>
    </div>
  );
}

function MetaRow({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="grid gap-1 sm:grid-cols-[140px_1fr]">
      <dt className="text-slate-500">{label}</dt>
      <dd className="break-all font-medium text-ink">{value || "无"}</dd>
    </div>
  );
}

function SummaryNumber({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "neutral" | "success" | "danger";
}) {
  const color = tone === "success" ? "text-emerald-700" : tone === "danger" ? "text-red-700" : "text-ink";
  return (
    <div className="rounded-md border border-line bg-slate-50 p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`mt-2 text-2xl font-semibold ${color}`}>{value}</p>
    </div>
  );
}

function CaseResultRow({ item }: { item: EvaluationCaseResult }) {
  return (
    <tr>
      <td className="py-3 pr-4 font-mono text-xs text-slate-700">{item.case_id}</td>
      <td className="py-3 pr-4">{displayLabel(item.category)}</td>
      <td className="py-3 pr-4">
        <div className="flex flex-wrap gap-1">
          {item.failure_reasons.map((reason) => (
            <Badge key={reason} tone="danger">
              {displayLabel(reason)}
            </Badge>
          ))}
        </div>
      </td>
      <td className="py-3 pr-4 text-slate-600">{summarizeActual(item)}</td>
    </tr>
  );
}

function TraceCard({ item }: { item: EvaluationCaseResult }) {
  return (
    <div className="rounded-lg border border-line bg-slate-50 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-mono text-xs text-slate-500">{item.case_id}</p>
          <h3 className="mt-1 text-sm font-semibold text-ink">{displayLabel(item.category)}</h3>
        </div>
        <Badge tone={toneForStatusValue(item.success ? "completed" : "blocked")}>
          {item.success ? "通过" : "失败"}
        </Badge>
      </div>
      <dl className="mt-3 grid gap-2 text-sm">
        <MetaRow label="意图" value={displayLabel(stringActual(item, "intent"))} />
        <MetaRow label="建议" value={displayLabel(stringActual(item, "action_type"))} />
        <MetaRow label="风险" value={displayLabel(stringActual(item, "risk_level"))} />
        <MetaRow label="政策" value={policySummary(item)} />
      </dl>
    </div>
  );
}

function summarizeActual(item: EvaluationCaseResult): string {
  const status = stringActual(item, "status");
  const actionType = stringActual(item, "action_type");
  const blockedCode = stringActual(item, "blocked_code");
  if (blockedCode) {
    return `拦截原因：${displayLabel(blockedCode)}`;
  }
  return [status ? `状态：${displayLabel(status)}` : null, actionType ? `建议：${displayLabel(actionType)}` : null]
    .filter(Boolean)
    .join("；") || "无摘要";
}

function policySummary(item: EvaluationCaseResult): string {
  const raw = item.actual.policy_ids;
  if (!Array.isArray(raw) || raw.length === 0) {
    return "无政策依据";
  }
  return raw.map((value) => String(value)).join(", ");
}

function stringActual(item: EvaluationCaseResult, key: string): string | null {
  const value = item.actual[key];
  return typeof value === "string" ? value : null;
}

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "n/a";
  }
  return `${(value * 100).toFixed(1)}%`;
}

function isApiError(value: unknown): value is ApiError {
  return typeof value === "object" && value !== null && "status" in value;
}
