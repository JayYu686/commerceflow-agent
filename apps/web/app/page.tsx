"use client";
import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";

type Role = "operator" | "reviewer";
type Budget = {
  committed_yuan: number;
  admission_limit_yuan: number;
  task_budget_yuan: number;
};
type Event = {
  id: number;
  kind: string;
  payload: Record<string, unknown>;
  at: string;
};
type Case = {
  id: string;
  status: string;
  order_no: string | null;
  messages: { id: string; role: string; content: string }[];
  plan: {
    id: string;
    amount_fen: number;
    intent: string;
    item_id: string | null;
    policy_id: string;
    policy_text: string;
    defect_quote: string;
    checksum: string;
    requires_approval: boolean;
  } | null;
  approval: { approved: boolean; comment: string } | null;
  executions: {
    id: string;
    status: string;
    result: Record<string, unknown> | null;
  }[];
};
const status: Record<string, string> = {
  investigating: "正在调查",
  needs_information: "待补充信息",
  waiting_approval: "等待审核",
  waiting_confirmation: "等待执行确认",
  executing: "正在执行",
  completed: "已完成",
  result_uncertain: "结果待核验",
  rejected: "审核拒绝",
  stopped: "已停止",
  no_action: "未执行操作",
};
const names: Record<string, string> = {
  message_received: "收到售后诉求",
  job_started: "开始处理",
  tool_completed: "取得工具证据",
  tool_rejected: "工具调用被阻止",
  plan_submitted: "提交处置方案",
  approval_decided: "审核已记录",
  execution_confirmed: "客服确认执行",
  execution_succeeded: "业务执行成功",
  job_uncertain: "正在核验结果",
  job_stopped: "处理停止",
  assistant_message: "助手回复",
};
const receiptLabels: Record<string, string> = {
  execution_id: "执行编号", ticket_id: "售后工单", order_no: "订单号",
  item_id: "商品行", amount_fen: "本次金额", refunded_fen: "累计退款",
  coupon_code: "优惠券编号", status: "业务状态", simulated: "模拟业务",
  order_refunded_fen: "订单累计退款", resolution: "处理结果",
  intent: "处理类型", entitlement_key: "权益编号",
};
function receiptValue(key: string, value: unknown) {
  if (key.endsWith("_fen") && typeof value === "number") return `¥${(value / 100).toFixed(2)}`;
  if (key === "simulated") return value ? "是（不接入真实支付）" : "否";
  if (value === "succeeded") return "已成功";
  if (value === "refund_succeeded") return "退款已入模拟账本";
  if (value === "coupon_issued") return "模拟优惠券已发放";
  if (value === "quality_issue_refund") return "商品质量退款";
  if (value === "logistics_delay_compensation") return "物流延误补偿";
  return String(value);
}
async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method: body === undefined ? "GET" : "POST",
    credentials: "same-origin",
    headers:
      body === undefined
        ? {}
        : {
            "Content-Type": "application/json",
            "X-Requested-With": "CommerceFlow",
            "Idempotency-Key": crypto.randomUUID(),
          },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      data.message ||
        JSON.stringify(data.detail) ||
        `请求失败 ${response.status}`,
    );
  return data;
}
export default function Workbench() {
  const [role, setRole] = useState<Role | null>(null),
    [loginRole, setLoginRole] = useState<Role>("operator"),
    [password, setPassword] = useState("");
  const [model, setModel] = useState(""),
    [caseId, setCaseId] = useState<string | null>(null),
    [current, setCurrent] = useState<Case | null>(null);
  const [cases, setCases] = useState<
      { id: string; status: string; order_no: string | null }[]
    >([]),
    [events, setEvents] = useState<Event[]>([]);
  const [message, setMessage] = useState(""),
    [comment, setComment] = useState(""),
    [checked, setChecked] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [budget, setBudget] = useState<Budget | null>(null);
  function selectCase(id: string | null) {
    setCaseId(id);
    setCurrent(null);
    setEvents([]);
    setChecked(false);
    setComment("");
  }
  const refresh = useCallback(async () => {
    const list = await api<typeof cases>("/cases");
    setCases(list);
    setBudget(await api<Budget>("/budget"));
    if (caseId) {
      const view = await api<Case>(`/cases/${caseId}`);
      setCurrent(view);
    }
  }, [caseId]);
  useEffect(() => {
    api<{ role: Role; model: string }>("/session")
      .then((s) => {
        setRole(s.role);
        setModel(s.model);
      })
      .catch(() => {});
  }, []);
  useEffect(() => {
    if (!role) return;
    api<typeof cases>("/cases").then(setCases).catch((e) => setError(e.message));
    if (caseId) api<Case>(`/cases/${caseId}`).then(setCurrent).catch((e) => setError(e.message));
    api<Budget>("/budget").then(setBudget).catch(() => setBudget(null));
    const timer = setInterval(() => refresh().catch(() => {}), 3000);
    return () => clearInterval(timer);
  }, [role, refresh, caseId]);
  useEffect(() => {
    if (!role || !caseId) return;
    const stream = new EventSource(`/api/cases/${caseId}/events`);
    stream.onmessage = (e) => {
      const item = JSON.parse(e.data) as Event;
      setEvents((previous) =>
        previous.some((x) => x.id === item.id) ? previous : [...previous, item],
      );
    };
    return () => stream.close();
  }, [role, caseId]);
  async function action(work: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await work();
    } catch (e) {
      setError(e instanceof Error ? e.message : "请求失败");
    } finally {
      setBusy(false);
    }
  }
  async function login(e: FormEvent) {
    e.preventDefault();
    await action(async () => {
      const s = await api<{ role: Role }>("/session", {
        role: loginRole,
        password,
      });
      setPassword("");
      setRole(s.role);
      setModel((await api<{ model: string }>("/session")).model);
    });
  }
  async function send(e: FormEvent) {
    e.preventDefault();
    await action(async () => {
      const r = await api<{ case_id: string }>(
        caseId ? `/cases/${caseId}/messages` : "/cases",
        { content: message },
      );
      if (r.case_id !== caseId) selectCase(r.case_id);
      setMessage("");
      setCurrent(await api(`/cases/${r.case_id}`));
    });
  }
  const active =
    !!current &&
    ["investigating", "executing", "result_uncertain"].includes(current.status);
  return (
    <div>
      <header className="topbar">
        <Link className="brand" href="/">
          CF<span>CommerceFlow</span>
          <small>AGENT WORKSPACE / V2</small>
        </Link>
        <div className="identity">
          <i />
          模拟业务环境{" "}
          {role && (
            <>
              <b>{role === "operator" ? "客服" : "审核员"}</b>
              <button
                className="text-button"
                onClick={() =>
                  action(async () => {
                    await api("/logout", {});
                    setRole(null);
                  })
                }
              >
                退出
              </button>
            </>
          )}
        </div>
      </header>
      {!role ? (
        <main className="login-layout">
          <section>
            <span className="eyebrow">GROUNDED. REVIEWED. EXECUTED.</span>
            <h1>
              让每一次售后处理，
              <br />
              都有依据、有结果。
            </h1>
            <p>
              Agent
              查询订单与政策，人工审核业务方案，受控执行器完成退款与补偿。每一步都可核验。
            </p>
            <div className="steps">
              <span>01 事实调查</span>
              <span>02 人工审核</span>
              <span>03 确认执行</span>
            </div>
          </section>
          <form className="login-card" onSubmit={login}>
            <h2>进入演示工作台</h2>
            <p>使用部署时配置的演示账号。</p>
            <label>
              工作角色
              <select
                value={loginRole}
                onChange={(e) => setLoginRole(e.target.value as Role)}
              >
                <option value="operator">客服 · 调查与确认执行</option>
                <option value="reviewer">审核员 · 核实证据与审批</option>
              </select>
            </label>
            <label>
              密码
              <input
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
            {error && (
              <p role="alert" className="error">
                {error}
              </p>
            )}
            {current?.status === "stopped" && events.filter(e => e.kind === "job_stopped").slice(-1).map(e => (
              <div role="status" className="error" key={e.id}>
                调查已停止：{String(e.payload.message || "请查看处理时间线")}
                {e.payload.code ? `（${String(e.payload.code)}）` : ""}
              </div>
            ))}
            <button className="primary" disabled={busy}>
              登录
            </button>
            <small>所有订单、退款和优惠券均为模拟数据。</small>
          </form>
        </main>
      ) : (
        <main className="workspace">
          <aside className="sidebar">
            <div className="section-label">
              售后案件
              <button
                className="text-button"
                onClick={() => {
                  selectCase(null);
                  setMessage("");
                }}
              >
                ＋ 新建
              </button>
            </div>
            <div className="case-list">
              {cases.map((c) => (
                <button
                  className={`case-link ${c.id === caseId ? "selected" : ""}`}
                  key={c.id}
                  onClick={() => selectCase(c.id)}
                >
                  <strong>{c.order_no || "待确认订单"}</strong>
                  <span>{status[c.status] || c.status}</span>
                  <small>{c.id.slice(0, 8)}</small>
                </button>
              ))}
              {!cases.length && (
                <p className="muted">提交诉求后，案件会显示在这里。</p>
              )}
            </div>
            <div className="runtime">
              <span className="eyebrow">运行信息</span>
              <p>{model}</p>
              <small>
                DeepSeek 已结算及预留
                <br />{budget ? `¥${budget.committed_yuan.toFixed(3)} / ¥${budget.admission_limit_yuan.toFixed(2)}` : "预算账本暂不可用"}
                <br />
                {budget ? `总预算 ¥${budget.task_budget_yuan}` : "总预算待查询"} · 无自动模型切换
              </small>
            </div>
          </aside>
          <section className="main-panel">
            <div className="page-heading">
              <div>
                <span className="eyebrow">AFTER-SALES OPERATIONS</span>
                <h1>{current?.order_no || "售后工作台"}</h1>
              </div>
              <span className="status">
                {current
                  ? status[current.status] || current.status
                  : "新建案件"}
              </span>
            </div>
            {error && (
              <div role="alert" className="error">
                {error}
              </div>
            )}
            {!current && (
              <div className="welcome">
                <h2>从一个真实诉求开始</h2>
                <p>说明订单和问题。信息不足时，Agent 会继续询问。</p>
                <div className="scenario-grid">
                  <button
                    onClick={() =>
                      setMessage(
                        "订单 CF000001 的蓝牙耳机左耳没有声音，我想退这个耳机的钱。收纳包没有问题。",
                      )
                    }
                  >
                    商品质量退款<span>多商品订单 · 按商品行退款</span>
                  </button>
                  <button
                    onClick={() =>
                      setMessage(
                        "订单 CF000002 五天没有物流更新了，请帮我查询是否可以补偿。",
                      )
                    }
                  >
                    物流延误补偿<span>真实轨迹 · 一次性补偿权益</span>
                  </button>
                </div>
              </div>
            )}
            <div className="conversation">
              {current?.messages.map((m) => (
                <div className={`message ${m.role}`} key={m.id}>
                  <span>{m.role === "user" ? "客服提交" : "调查助手"}</span>
                  <p>{m.content}</p>
                </div>
              ))}
            </div>
            {current?.plan && (
              <article className="plan-card">
                <div className="section-label">
                  {current.status === "completed" ? "已执行方案" : "待执行方案"}
                  <span>
                    {current.plan.requires_approval
                      ? "须人工审核"
                      : "免审核 · 须确认"}
                  </span>
                </div>
                <h2>
                  {current.plan.intent === "quality_issue_refund"
                    ? "商品行退款"
                    : "物流延误补偿"}
                  <strong>¥{(current.plan.amount_fen / 100).toFixed(2)}</strong>
                </h2>
                <p>处理商品：{current.plan.item_id || "订单物流补偿"}</p>
                {current.plan.defect_quote && (
                  <blockquote>
                    用户证据：“{current.plan.defect_quote}”
                  </blockquote>
                )}
                <details open>
                  <summary>政策依据 · {current.plan.policy_id}</summary>
                  <p>{current.plan.policy_text}</p>
                </details>
                <small>
                  方案版本 {current.plan.checksum.slice(0, 16)} ·
                  内容改变后须重新授权
                </small>
                {current.approval && (
                  <p className="approval-note">
                    {current.approval.approved ? "已批准" : "已拒绝"} ·{" "}
                    {current.approval.comment}
                  </p>
                )}
                {role === "reviewer" &&
                  current.status === "waiting_approval" && (
                    <div className="approval-form">
                      <label className="checkbox">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={(e) => setChecked(e.target.checked)}
                        />
                        已核实故障证据、商品范围及人为损坏/擅自维修等排除条款
                      </label>
                      <label>
                        审核意见
                        <textarea
                          value={comment}
                          onChange={(e) => setComment(e.target.value)}
                          placeholder="填写核实依据，至少4个字"
                        />
                      </label>
                      <div className="button-row">
                        <button
                          className="primary"
                          disabled={busy || !checked || comment.length < 4}
                          onClick={() =>
                            action(async () => {
                              await api(`/plans/${current.plan!.id}/approval`, {
                                approved: true,
                                comment,
                                evidence_checked: checked,
                              });
                              await refresh();
                            })
                          }
                        >
                          批准此版本方案
                        </button>
                        <button
                          disabled={busy || comment.length < 4}
                          onClick={() =>
                            action(async () => {
                              await api(`/plans/${current.plan!.id}/approval`, {
                                approved: false,
                                comment,
                                evidence_checked: checked,
                              });
                              await refresh();
                            })
                          }
                        >
                          拒绝
                        </button>
                      </div>
                    </div>
                  )}
                {role === "operator" &&
                  current.status === "waiting_confirmation" && (
                    <button
                      className="primary confirm"
                      disabled={busy}
                      onClick={() =>
                        action(async () => {
                          await api(`/plans/${current.plan!.id}/confirmation`, {
                            confirmed: true,
                          });
                          await refresh();
                        })
                      }
                    >
                      确认执行 ¥{(current.plan.amount_fen / 100).toFixed(2)}{" "}
                      模拟
                      {current.plan.intent === "quality_issue_refund"
                        ? "退款"
                        : "补偿"}
                    </button>
                  )}
              </article>
            )}
            {current?.executions.map((ex) => (
              <article className="result-card" key={ex.id}>
                <span className="eyebrow">业务凭证</span>
                <h2>
                  {ex.status === "succeeded"
                    ? "执行成功"
                    : ex.status === "uncertain"
                      ? "结果待核验，请勿重复申请"
                      : "执行状态：" + ex.status}
                </h2>
                <dl>
                  {Object.entries(ex.result || {})
                    .filter(([, v]) => v !== null)
                    .map(([k, v]) => (
                      <div key={k}>
                        <dt>{receiptLabels[k] || k}</dt>
                        <dd>{receiptValue(k, v)}</dd>
                      </div>
                    ))}
                </dl>
              </article>
            ))}
            {role === "operator" && (
              <form className="composer" onSubmit={send}>
                <label htmlFor="message">
                  {caseId ? "补充信息（未执行的旧方案将失效）" : "售后诉求"}
                </label>
                <textarea
                  id="message"
                  required
                  maxLength={6000}
                  value={message}
                  disabled={active}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="例如：订单 CF000001 的耳机左耳没有声音，想申请退款。"
                />
                <div>
                  <small>仅操作模拟业务 · 不接入真实支付</small>
                  <button
                    className="primary"
                    disabled={busy || active || !message.trim()}
                  >
                    {active ? "正在处理…" : "提交调查"}
                  </button>
                </div>
              </form>
            )}
          </section>
          <aside className="timeline">
            <div className="section-label">
              处理时间线<span>{events.length} 个事件</span>
            </div>
            {!events.length && (
              <p className="muted">工具证据、审核与执行结果将实时显示。</p>
            )}
            {events.map((e) => (
              <details className="event" key={e.id}>
                <summary>
                  <span>{names[e.kind] || e.kind}</span>
                  <time>{new Date(e.at).toLocaleTimeString("zh-CN")}</time>
                </summary>
                <pre>{JSON.stringify(e.payload, null, 2)}</pre>
              </details>
            ))}
          </aside>
        </main>
      )}
    </div>
  );
}
