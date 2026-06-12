"use client";

import { useEffect, useMemo, useState } from "react";

import { Badge } from "../../components/console/Badge";
import { DebugJson } from "../../components/console/DebugJson";
import { ErrorNotice } from "../../components/console/ErrorNotice";
import { IdempotencyKeyBox } from "../../components/console/IdempotencyKeyBox";
import { Panel } from "../../components/console/Panel";
import { createActionPlan, getActionPlan, getHealth, runPreview } from "../../lib/api";
import { DEFAULT_AS_OF_LOCAL, DEMO_SCENARIOS } from "../../lib/demo-scenarios";
import {
  displayLabel,
  displayWithRaw,
  fieldLabel,
  toneForRiskValue,
  toneForStatusValue,
  localizeText,
  policyExcerpt,
  policySection,
  policyTitle,
  sourceLabel,
  yesNo,
} from "../../lib/display";
import { newIdempotencyKey } from "../../lib/idempotency";
import type {
  ActionPlanCreateResponse,
  ActionPlanResponse,
  AgentPreviewRequest,
  AgentPreviewResponse,
  ApiError,
  DemoScenario,
  FactEvidence,
  HealthResponse,
  PolicyEvidence,
  WorkflowStep,
} from "../../lib/types";

type ActionPlanSource = "created" | "reused";

export default function WorkbenchPage() {
  const [selectedScenarioId, setSelectedScenarioId] = useState<DemoScenario["id"]>("quality_refund");
  const selectedScenario = useMemo(
    () => DEMO_SCENARIOS.find((scenario) => scenario.id === selectedScenarioId) ?? DEMO_SCENARIOS[0],
    [selectedScenarioId],
  );
  const [message, setMessage] = useState(selectedScenario.message);
  const [asOfLocal, setAsOfLocal] = useState(DEFAULT_AS_OF_LOCAL);
  const [preview, setPreview] = useState<AgentPreviewResponse | null>(null);
  const [actionPlan, setActionPlan] = useState<ActionPlanCreateResponse | null>(null);
  const [actionPlanSource, setActionPlanSource] = useState<ActionPlanSource | null>(null);
  const [idempotencyKey, setIdempotencyKey] = useState("");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<ApiError | Error | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [creatingActionPlan, setCreatingActionPlan] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const params = new URLSearchParams(window.location.search);
      const scenarioId = params.get("scenario") as DemoScenario["id"] | null;
      const scenario = DEMO_SCENARIOS.find((item) => item.id === scenarioId);
      if (scenario) {
        chooseScenario(scenario);
      } else {
        setIdempotencyKey(newIdempotencyKey("web-action-plan"));
      }
    }, 0);
    getHealth()
      .then(setHealth)
      .catch((caught: unknown) => setError(normalizeThrown(caught)));
    return () => window.clearTimeout(timer);
  }, []);

  function chooseScenario(scenario: DemoScenario) {
    setSelectedScenarioId(scenario.id);
    setMessage(scenario.message);
    setPreview(null);
    setActionPlan(null);
    setActionPlanSource(null);
    setError(null);
    setIdempotencyKey(newIdempotencyKey("web-action-plan"));
  }

  function resetWorkbench() {
    setMessage(selectedScenario.message);
    setAsOfLocal(DEFAULT_AS_OF_LOCAL);
    setPreview(null);
    setActionPlan(null);
    setActionPlanSource(null);
    setError(null);
    setIdempotencyKey(newIdempotencyKey("web-action-plan"));
  }

  async function submitPreview() {
    setLoadingPreview(true);
    setError(null);
    setActionPlan(null);
    setActionPlanSource(null);
    try {
      const response = await runPreview(buildRequest(message, asOfLocal));
      setPreview(response);
    } catch (caught: unknown) {
      setPreview(null);
      setError(normalizeThrown(caught));
    } finally {
      setLoadingPreview(false);
    }
  }

  async function submitActionPlan() {
    if (!idempotencyKey) {
      setError(new Error("正在生成幂等键，请稍后再创建 Action Plan。"));
      return;
    }

    setCreatingActionPlan(true);
    setError(null);
    try {
      const response = await createActionPlan(buildRequest(message, asOfLocal), idempotencyKey);
      setActionPlan(response);
      setActionPlanSource("created");
    } catch (caught: unknown) {
      const normalized = normalizeThrown(caught);
      if (isDuplicateActionPlanError(normalized)) {
        try {
          const existing = await getActionPlan(normalized.existing_identifier);
          setActionPlan(actionPlanResponseToCreateResponse(existing));
          setActionPlanSource("reused");
        } catch {
          setActionPlan(null);
          setActionPlanSource(null);
        }
      }
      setError(normalized);
    } finally {
      setCreatingActionPlan(false);
    }
  }

  const mismatches = useMemo(
    () => evaluateScenario(selectedScenario, preview, actionPlan, actionPlanSource),
    [selectedScenario, preview, actionPlan, actionPlanSource],
  );

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <header className="flex flex-col gap-4 border-b border-line pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-signal">Agent 工作台</p>
          <h2 className="mt-1 text-3xl font-semibold tracking-tight">
            预览、证据、风险与动作计划
          </h2>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
            从浏览器输入售后诉求并运行 Agent 预览。此页面可以创建动作计划，但不能审批、
            执行工具、调用 MCP，或修改订单、物流和政策记录。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge tone={health?.status === "ok" ? "success" : "warning"}>
            API {health?.status ?? "未知"}
          </Badge>
          <Badge tone="warning">创建动作计划前仅预览</Badge>
          <Badge tone="neutral">不调用真实外部系统</Badge>
        </div>
      </header>

      <div className="grid gap-6 xl:grid-cols-[420px_1fr]">
        <div className="space-y-6">
          <Panel title="场景选择" eyebrow="演示输入">
            <div className="grid gap-3">
              {DEMO_SCENARIOS.map((scenario) => (
                <button
                  key={scenario.id}
                  type="button"
                  onClick={() => chooseScenario(scenario)}
                  className={`rounded-lg border p-4 text-left transition ${
                    scenario.id === selectedScenario.id
                      ? "border-signal bg-teal-50"
                      : "border-line bg-white hover:border-signal"
                  }`}
                >
                  <div className="font-semibold text-ink">{scenario.title}</div>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{scenario.message}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {scenario.expected.map((item) => (
                      <Badge key={item} tone="info">
                        {item}
                      </Badge>
                    ))}
                  </div>
                </button>
              ))}
            </div>
          </Panel>

          <Panel title="请求输入" eyebrow="预览参数">
            <form
              className="space-y-4"
              onSubmit={(event) => {
                event.preventDefault();
                void submitPreview();
              }}
            >
              <label className="block">
                <span className="text-sm font-medium text-slate-700">用户售后诉求</span>
                <textarea
                  value={message}
                  onChange={(event) => setMessage(event.target.value)}
                  rows={6}
                  className="mt-2 w-full rounded-lg border border-line bg-white p-3 text-sm leading-6 text-ink outline-none focus:border-signal focus:ring-2 focus:ring-teal-100"
                />
              </label>
              <label className="block">
                <span className="text-sm font-medium text-slate-700">业务时间 as_of</span>
                <input
                  type="datetime-local"
                  value={asOfLocal}
                  onChange={(event) => setAsOfLocal(event.target.value)}
                  className="mt-2 w-full rounded-lg border border-line bg-white p-3 text-sm text-ink outline-none focus:border-signal focus:ring-2 focus:ring-teal-100"
                />
                <span className="mt-1 block text-xs text-slate-500">
                  提交时会转换为带时区的 ISO 8601 字符串，避免向后端发送无时区时间。
                </span>
              </label>
              <div className="flex flex-wrap gap-2">
                <button
                  type="submit"
                  disabled={loadingPreview || !message.trim()}
                  className="rounded-md bg-signal px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800 disabled:cursor-not-allowed disabled:bg-slate-300"
                >
                  {loadingPreview ? "正在运行预览..." : "运行预览"}
                </button>
                <button
                  type="button"
                  onClick={resetWorkbench}
                  className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
                >
                  清空 / 重置
                </button>
              </div>
            </form>
          </Panel>

          <ErrorNotice error={error} />
        </div>

        <div className="space-y-6">
          <SummaryPanel preview={preview} />
          <ScenarioCheck
            mismatches={mismatches}
            preview={preview}
            actionPlan={actionPlan}
            actionPlanSource={actionPlanSource}
          />
          <StepTimeline steps={preview?.steps ?? []} />
          <FactsPanel preview={preview} />
          <PolicyPanel evidence={preview?.policy_evidence ?? []} />
          <RecommendationPanel preview={preview} />
          <CustomerReplyPanel preview={preview} />
          <LLMPanel preview={preview} />
          <ActionPlanPanel
            preview={preview}
            actionPlan={actionPlan}
            idempotencyKey={idempotencyKey}
            creating={creatingActionPlan}
            onCreate={() => void submitActionPlan()}
            onRefreshKey={() => {
              setIdempotencyKey(newIdempotencyKey("web-action-plan"));
              setActionPlan(null);
              setActionPlanSource(null);
            }}
            actionPlanSource={actionPlanSource}
          />
          <DebugJson title="预览调试 JSON" data={preview ?? { message: "还没有运行预览。" }} />
          <DebugJson
            title="动作计划调试 JSON"
            data={actionPlan ?? { message: "还没有创建动作计划。" }}
          />
        </div>
      </div>
    </div>
  );
}

function SummaryPanel({ preview }: { preview: AgentPreviewResponse | null }) {
  return (
    <Panel title="运行摘要" eyebrow="预览结果">
      <div className="grid gap-3 md:grid-cols-5">
        <SummaryMetric
          label="状态"
          value={displayLabel(preview?.status, "未运行")}
          raw={preview?.status}
          tone={toneForStatusValue(preview?.status)}
        />
        <SummaryMetric
          label="意图"
          value={displayLabel(preview?.intent, "未识别")}
          raw={preview?.intent}
          tone="info"
        />
        <SummaryMetric label="订单" value={preview?.order_no ?? "未找到"} tone="neutral" />
        <SummaryMetric
          label="风险"
          value={displayLabel(preview?.risk.level, "未知")}
          raw={preview?.risk.level}
          tone={toneForRiskValue(preview?.risk.level)}
        />
        <SummaryMetric
          label="审批"
          value={preview?.risk.requires_approval ? "需要审批" : "无需审批"}
          raw={preview ? String(preview.risk.requires_approval) : null}
          tone={preview?.risk.requires_approval ? "warning" : "success"}
        />
      </div>
    </Panel>
  );
}

function ScenarioCheck({
  mismatches,
  preview,
  actionPlan,
  actionPlanSource,
}: {
  mismatches: string[];
  preview: AgentPreviewResponse | null;
  actionPlan: ActionPlanCreateResponse | null;
  actionPlanSource: ActionPlanSource | null;
}) {
  if (!preview && !actionPlan) {
    return null;
  }
  return (
    <Panel title="Demo 预期校验" eyebrow="场景验证">
      {actionPlanSource === "reused" && actionPlan ? (
        <div className="mb-3 rounded-lg border border-sky-200 bg-sky-50 p-4 text-sm leading-6 text-sky-900">
          已复用历史动作计划，当前状态为
          <span className="mx-1 font-semibold">{displayLabel(actionPlan.status)}</span>。
          Demo 中“待审批”的预期只适用于首次新建动作计划；复用历史计划时，以后端返回的真实状态为准。
        </div>
      ) : null}
      {mismatches.length === 0 ? (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
          当前结果与该 Demo 在当前步骤的预期一致。
        </div>
      ) : (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <div className="font-semibold">发现预期不一致</div>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {mismatches.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}
    </Panel>
  );
}

function StepTimeline({ steps }: { steps: WorkflowStep[] }) {
  return (
    <Panel title="Agent 步骤时间线" eyebrow="LangGraph 预览">
      {steps.length === 0 ? (
        <EmptyState message="运行预览后，这里会展示确定性解析、事实查询、政策检索和风险判断步骤。" />
      ) : (
        <ol className="space-y-3">
          {steps.map((step, index) => {
            const stepName = displayWithRaw(step.name);
            return (
              <li key={`${step.name}-${index}`} className="flex gap-3">
                <div className="flex flex-col items-center">
                  <div className="grid h-7 w-7 place-items-center rounded-full bg-slate-900 text-xs font-semibold text-white">
                    {index + 1}
                  </div>
                  {index < steps.length - 1 ? <div className="h-full w-px bg-line" /> : null}
                </div>
                <div className="min-w-0 flex-1 rounded-lg border border-line bg-slate-50 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-ink">{stepName.label}</span>
                    <Badge tone={toneForStatusValue(step.status)}>{displayLabel(step.status)}</Badge>
                  </div>
                  {stepName.raw ? (
                    <div className="mt-1 text-xs text-slate-500">原始步骤：{stepName.raw}</div>
                  ) : null}
                  <p className="mt-2 text-sm text-slate-600">{localizeText(step.detail)}</p>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </Panel>
  );
}

function FactsPanel({ preview }: { preview: AgentPreviewResponse | null }) {
  const order = preview?.facts.order;
  const logistics = preview?.facts.logistics;
  return (
    <Panel title="订单与物流事实" eyebrow="事实依据">
      {!order && !logistics ? (
        <EmptyState message="运行预览后，这里会展示后端事实查询结果。" />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-lg border border-line bg-slate-50 p-4">
            <h3 className="font-semibold">订单事实</h3>
            {order ? (
              <dl className="mt-3 grid gap-2 text-sm">
                <KeyValue label="订单号" value={order.order_no} />
                <KeyValue label="订单状态" value={displayLabel(order.status)} raw={order.status} />
                <KeyValue
                  label="售后状态"
                  value={displayLabel(order.aftersales_status)}
                  raw={order.aftersales_status}
                />
                <KeyValue label="支付金额" value={`${order.currency} ${order.paid_amount}`} />
                <KeyValue label="签收时间" value={order.delivered_at ?? "未签收"} />
                <KeyValue label="客户" value={`${order.customer.name} (${order.customer.tier})`} />
                <div className="mt-2">
                  <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    商品明细
                  </div>
                  <ul className="mt-2 space-y-2">
                    {order.items.map((item) => (
                      <li key={item.product.sku} className="rounded border border-line bg-white p-2">
                        <div className="font-medium">{item.product.name}</div>
                        <div className="text-xs text-slate-500">
                          {item.product.sku} · {displayLabel(item.product.category)} ·{" "}
                          {displayLabel(item.product.aftersales_type)}
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              </dl>
            ) : (
              <EmptyState message="未返回订单事实。" />
            )}
          </div>
          <div className="rounded-lg border border-line bg-slate-50 p-4">
            <h3 className="font-semibold">物流事实</h3>
            {logistics ? (
              <dl className="mt-3 grid gap-2 text-sm">
                <KeyValue label="承运商" value={logistics.carrier} />
                <KeyValue label="运单号" value={logistics.tracking_no} />
                <KeyValue label="物流状态" value={displayLabel(logistics.status)} raw={logistics.status} />
                <KeyValue label="承诺送达" value={logistics.promised_at} />
                <KeyValue label="最后事件" value={logistics.last_event_at ?? "暂无"} />
                <div className="mt-2">
                  <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    物流事件
                  </div>
                  <ul className="mt-2 space-y-2">
                    {logistics.events.slice(0, 5).map((event) => (
                      <li key={event.sequence} className="rounded border border-line bg-white p-2">
                        <div className="font-medium">
                          #{event.sequence} {displayLabel(event.event_type)}
                        </div>
                        <div className="text-xs text-slate-500">
                          {event.occurred_at} · {localizeText(event.location)}
                        </div>
                        <p className="mt-1 text-sm text-slate-600">
                          {localizeText(event.description)}
                        </p>
                      </li>
                    ))}
                  </ul>
                </div>
              </dl>
            ) : (
              <EmptyState message="未返回物流事实。" />
            )}
          </div>
        </div>
      )}
      {preview?.fact_evidence.length ? <FactEvidenceList evidence={preview.fact_evidence} /> : null}
    </Panel>
  );
}

function PolicyPanel({ evidence }: { evidence: PolicyEvidence[] }) {
  return (
    <Panel title="政策依据" eyebrow="RAG 检索">
      {evidence.length === 0 ? (
        <EmptyState message="当前还没有命中的政策依据。无政策依据时不能编造执行建议。" />
      ) : (
        <div className="grid gap-3">
          {evidence.map((policy) => (
            <article key={policy.chunk_id} className="rounded-lg border border-line bg-slate-50 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold">{policy.policy_id}</span>
                <Badge tone="info">{policy.section}</Badge>
                <Badge tone="neutral">相关度 {policy.score.toFixed(3)}</Badge>
              </div>
              <div className="mt-2 text-sm text-slate-600">
                {policyTitle(policy.title)} · {policy.version} · {displayLabel(policy.category)} /{" "}
                {displayLabel(policy.aftersales_type)}
              </div>
              <p className="mt-3 text-sm leading-6 text-slate-700">
                {policyExcerpt(policy.content_excerpt)}
              </p>
              <div className="mt-2 text-xs text-slate-500">
                政策章节：{policySection(policy.section)} · 原始章节：{policy.section}
              </div>
            </article>
          ))}
        </div>
      )}
    </Panel>
  );
}

function RecommendationPanel({ preview }: { preview: AgentPreviewResponse | null }) {
  const recommendation = preview?.recommendation;
  const risk = preview?.risk;
  return (
    <Panel title="处理建议与风险" eyebrow="仅预览，不执行">
      {!recommendation || !risk ? (
        <EmptyState message="运行预览后，这里会展示建议动作、风险等级和后续步骤。" />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
          <div className="rounded-lg border border-line bg-slate-50 p-4">
            <div className="flex flex-wrap gap-2">
              <Badge tone={toneForStatusValue(recommendation.action_status)}>
                {displayLabel(recommendation.action_status)}
              </Badge>
              <Badge tone="info">{displayLabel(recommendation.action_type)}</Badge>
              <Badge tone={toneForRiskValue(risk.level)}>风险：{displayLabel(risk.level)}</Badge>
              <Badge tone={risk.requires_approval ? "warning" : "success"}>
                人工审批：{yesNo(risk.requires_approval)}
              </Badge>
            </div>
            <p className="mt-4 text-sm leading-6 text-slate-700">
              {localizeText(recommendation.summary)}
            </p>
            {recommendation.proposed_amount ? (
              <div className="mt-3 text-sm font-semibold">
                预估金额：{recommendation.currency} {recommendation.proposed_amount}
              </div>
            ) : null}
            <div className="mt-2 text-xs text-slate-500">
              原始枚举：{recommendation.action_type} / {recommendation.action_status}
            </div>
          </div>
          <div className="rounded-lg border border-line bg-white p-4">
            <h3 className="text-sm font-semibold">风险原因</h3>
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-slate-700">
              {risk.reasons.map((reason) => (
                <li key={reason}>{localizeText(reason)}</li>
              ))}
            </ul>
          </div>
          <ListBlock title="建议原因" items={recommendation.reasons.map(localizeText)} />
          <ListBlock title="后续步骤" items={recommendation.next_steps.map(localizeText)} />
        </div>
      )}
    </Panel>
  );
}

function CustomerReplyPanel({ preview }: { preview: AgentPreviewResponse | null }) {
  return (
    <Panel title="面向用户回复" eyebrow="基于事实和政策">
      {preview ? (
        <div className="rounded-lg border border-line bg-slate-50 p-4 text-sm leading-7 text-slate-800">
          {preview.customer_reply}
        </div>
      ) : (
        <EmptyState message="运行预览后，这里会展示面向用户的回复。回复不能承诺已经退款、赔付或创建真实工单。" />
      )}
    </Panel>
  );
}

function LLMPanel({ preview }: { preview: AgentPreviewResponse | null }) {
  const llm = preview?.llm;
  return (
    <Panel title="LLM 元信息" eyebrow="受控模型适配器">
      {!llm ? (
        <EmptyState message="运行预览后，这里会展示模型供应方、是否回退、token 和延迟元信息。" />
      ) : (
        <div className="grid gap-3 md:grid-cols-4">
          <SummaryMetric label="模型供应方" value={displayLabel(llm.provider)} raw={llm.provider} tone="info" />
          <SummaryMetric
            label="是否回退"
            value={llm.fallback_used ? "已回退" : "未回退"}
            raw={String(llm.fallback_used)}
            tone={llm.fallback_used ? "warning" : "success"}
          />
          <SummaryMetric
            label="回退原因"
            value={displayLabel(llm.fallback_reason, "无")}
            raw={llm.fallback_reason}
            tone="neutral"
          />
          <SummaryMetric
            label="延迟"
            value={llm.latency_ms === null ? "n/a" : `${llm.latency_ms} ms`}
            tone="neutral"
          />
        </div>
      )}
    </Panel>
  );
}

function ActionPlanPanel({
  preview,
  actionPlan,
  idempotencyKey,
  creating,
  onCreate,
  onRefreshKey,
  actionPlanSource,
}: {
  preview: AgentPreviewResponse | null;
  actionPlan: ActionPlanCreateResponse | null;
  idempotencyKey: string;
  creating: boolean;
  onCreate: () => void;
  onRefreshKey: () => void;
  actionPlanSource: ActionPlanSource | null;
}) {
  const canCreate = Boolean(preview && idempotencyKey && !creating);
  return (
    <Panel title="创建动作计划（Action Plan）" eyebrow="持久化计划">
      <div className="space-y-4">
        <p className="text-sm leading-6 text-slate-600">
          创建动作计划会复用当前预览的用户请求和 as_of 业务时间。它只保存动作计划，不会批准、
          执行退款、发放优惠券、创建真实工单或调用 MCP 工具。
        </p>
        <IdempotencyKeyBox value={idempotencyKey} onRefresh={onRefreshKey} />
        <button
          type="button"
          disabled={!canCreate}
          onClick={onCreate}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {creating
            ? "正在创建动作计划..."
            : actionPlan
              ? "使用相同幂等键重试"
              : "创建动作计划"}
        </button>
        {!idempotencyKey ? (
          <div className="text-xs text-amber-700">正在生成幂等键，生成前不能创建动作计划。</div>
        ) : null}
        {actionPlan ? (
          <div className="space-y-3">
            {actionPlanSource === "reused" ? (
              <div className="rounded-lg border border-sky-200 bg-sky-50 p-3 text-sm leading-6 text-sky-900">
                后端检测到相同业务请求已存在动作计划，本次展示的是已复用的历史计划。这是业务防重复保护，
                不是系统错误。
              </div>
            ) : null}
            <div className="grid gap-3 rounded-lg border border-line bg-slate-50 p-4 text-sm md:grid-cols-2">
              <KeyValue label="动作计划 ID" value={actionPlan.action_plan_id} />
              <KeyValue label="审批 ID" value={actionPlan.approval_id ?? "无"} />
              <KeyValue
                label="来源"
                value={actionPlanSource === "reused" ? "复用历史动作计划" : "本次新建动作计划"}
              />
              <KeyValue
                label="动作类型"
                value={displayLabel(actionPlan.action_type)}
                raw={actionPlan.action_type}
              />
              <KeyValue label="计划工具" value={actionPlan.planned_tool_name ?? "无"} />
              <KeyValue label="状态" value={displayLabel(actionPlan.status)} raw={actionPlan.status} />
              <KeyValue
                label="执行状态"
                value={displayLabel(actionPlan.execution_status)}
                raw={actionPlan.execution_status}
              />
              <KeyValue
                label="风险等级"
                value={displayLabel(actionPlan.risk_level)}
                raw={actionPlan.risk_level}
              />
              <KeyValue
                label="金额"
                value={
                  actionPlan.proposed_amount
                    ? `${actionPlan.currency ?? ""} ${actionPlan.proposed_amount}`.trim()
                    : "无"
                }
              />
            </div>
          </div>
        ) : null}
      </div>
    </Panel>
  );
}

function FactEvidenceList({ evidence }: { evidence: FactEvidence[] }) {
  return (
    <div className="mt-4 rounded-lg border border-line bg-white p-4">
      <h3 className="text-sm font-semibold">事实依据字段</h3>
      <div className="mt-3 flex flex-wrap gap-2">
        {evidence.map((item) => (
          <Badge key={`${item.source}-${item.field}-${item.value}`} tone="neutral">
            {sourceLabel(item.source)} · {fieldLabel(item.field)}：{displayLabel(item.value)}
          </Badge>
        ))}
      </div>
    </div>
  );
}

function SummaryMetric({
  label,
  value,
  raw,
  tone,
}: {
  label: string;
  value: string;
  raw?: string | null;
  tone?: "neutral" | "success" | "warning" | "danger" | "critical" | "info";
}) {
  return (
    <div className="rounded-lg border border-line bg-slate-50 p-3">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-2">
        <Badge tone={tone}>{value}</Badge>
      </div>
      {raw && raw !== value ? <div className="mt-1 text-xs text-slate-500">{raw}</div> : null}
    </div>
  );
}

function KeyValue({ label, value, raw }: { label: string; value: string; raw?: string | null }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-1 break-words text-sm text-slate-800">{value}</dd>
      {raw && raw !== value ? <dd className="mt-0.5 text-xs text-slate-500">{raw}</dd> : null}
    </div>
  );
}

function ListBlock({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-lg border border-line bg-white p-4">
      <h3 className="text-sm font-semibold">{title}</h3>
      <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-slate-700">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-500">
      {message}
    </div>
  );
}

function buildRequest(message: string, asOfLocal: string): AgentPreviewRequest {
  const asOf = localDateTimeToIso(asOfLocal);
  return asOf ? { message, as_of: asOf } : { message };
}

function localDateTimeToIso(value: string): string | undefined {
  if (!value) {
    return undefined;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return undefined;
  }
  return date.toISOString();
}

function isDuplicateActionPlanError(error: ApiError | Error): error is ApiError & {
  existing_identifier: string;
} {
  return (
    "status" in error &&
    error.status === 409 &&
    error.code === "duplicate_action_plan" &&
    typeof error.existing_identifier === "string" &&
    error.existing_identifier.length > 0
  );
}

function actionPlanResponseToCreateResponse(
  response: ActionPlanResponse,
): ActionPlanCreateResponse {
  return {
    action_plan_id: response.action_plan_id,
    run_id: response.run_id,
    order_no: response.order_no,
    intent: response.intent,
    planned_tool_name: response.planned_tool_name,
    action_type: response.action_type,
    status: response.status,
    execution_status: response.execution_status,
    risk_level: response.risk_level,
    requires_approval: response.requires_approval,
    approval_id: response.approval?.approval_id ?? null,
    proposed_amount: response.proposed_amount,
    currency: response.currency,
    summary: response.summary,
    created_at: response.created_at,
  };
}

function evaluateScenario(
  scenario: DemoScenario,
  preview: AgentPreviewResponse | null,
  actionPlan: ActionPlanCreateResponse | null,
  actionPlanSource: ActionPlanSource | null,
): string[] {
  const mismatches: string[] = [];
  const expected = scenario.expectedPreview;
  if (preview) {
    if (expected.status && preview.status !== expected.status) {
      mismatches.push(
        `预期状态为 ${displayLabel(expected.status)}，实际为 ${displayLabel(preview.status)}。`,
      );
    }
    if (expected.intent && preview.intent !== expected.intent) {
      mismatches.push(
        `预期意图为 ${displayLabel(expected.intent)}，实际为 ${displayLabel(preview.intent)}。`,
      );
    }
    if (expected.recommendation && preview.recommendation.action_type !== expected.recommendation) {
      mismatches.push(
        `预期建议为 ${displayLabel(expected.recommendation)}，实际为 ${displayLabel(
          preview.recommendation.action_type,
        )}。`,
      );
    }
    if (expected.risk && preview.risk.level !== expected.risk) {
      mismatches.push(
        `预期风险为 ${displayLabel(expected.risk)}，实际为 ${displayLabel(preview.risk.level)}。`,
      );
    }
    if (
      expected.requiresApproval !== undefined &&
      preview.risk.requires_approval !== expected.requiresApproval
    ) {
      mismatches.push(
        `预期需要审批为 ${yesNo(expected.requiresApproval)}，实际为 ${yesNo(
          preview.risk.requires_approval,
        )}。`,
      );
    }
    if (
      expected.policyId &&
      !preview.policy_evidence.some((policy) => policy.policy_id === expected.policyId)
    ) {
      mismatches.push(`预期命中 ${policyIdTitleForScenario(expected.policyId)}，但实际未命中。`);
    }
  }
  if (
    actionPlan &&
    actionPlanSource !== "reused" &&
    expected.actionPlanStatus &&
    actionPlan.status !== expected.actionPlanStatus
  ) {
    mismatches.push(
      `预期 Action Plan 状态为 ${displayLabel(expected.actionPlanStatus)}，实际为 ${displayLabel(
        actionPlan.status,
      )}。`,
    );
  }
  return mismatches;
}

function policyIdTitleForScenario(policyId: string): string {
  if (policyId === "POL-LOGISTICS-DELAY-V1") {
    return "物流延迟补偿政策";
  }
  if (policyId === "POL-QUALITY-ELECTRONICS-V2") {
    return "电子产品质量问题退款政策";
  }
  return policyId;
}

function normalizeThrown(caught: unknown): ApiError | Error {
  if (caught instanceof Error) {
    return caught;
  }
  return caught as ApiError;
}
