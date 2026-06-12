# CommerceFlow Agent 简历项目总结

## 简历写法

**CommerceFlow Agent：可审批、可审计的电商售后业务智能体平台**

- 基于 FastAPI、SQLAlchemy、PostgreSQL/pgvector、LangGraph、Next.js 和 MCP 构建电商售后 Agent 演示系统，覆盖订单/物流事实查询、售后政策 RAG、Agent Preview、Action Plan、人工审批、Mock 工具执行和审计时间线。
- 设计受控 LLM Adapter，支持 disabled/fake/OpenAI-compatible Provider。真实模型只参与意图理解和用户回复措辞，不能覆盖订单事实、政策依据、风险结论、审批状态或工具执行。
- 实现 Action Plan、Approval Request、Audit Log、Mock Refund/Coupon/Ticket 结果表；所有写操作要求 `Idempotency-Key`，退款和高额补偿必须通过人工审批后才能进入 Mock 执行。
- 使用 stdio MCP Server 将 `refund_apply`、`coupon_issue`、`ticket_create` 暴露为薄工具包装层，所有审批、幂等、金额、订单和政策依据校验仍由内部 service 统一负责。
- 构建中文 Agent Operations Console，支持 Workbench、案例详情、审批中心、工具执行、审计时间线和评测看板，降低命令行依赖，便于业务演示和验收。
- 新增 100 条固定 MVP 评测集和 deterministic runner，生成 JSON/Markdown 报告。当前保存报告显示 Task Success Rate 94.00%，Unsafe Action Block Rate 100.00%，Approval Enforcement Rate 100.00%，Idempotency Protection Rate 100.00%。

## 技术栈

- 后端：Python 3.11、FastAPI、Pydantic、SQLAlchemy 2.x、Alembic。
- 数据：PostgreSQL、pgvector、Redis、deterministic seed。
- Agent：LangGraph、deterministic parser、controlled LLM adapter、OpenAI-compatible Chat Completions provider。
- RAG：结构化政策 JSON、deterministic embedding、pgvector cosine retrieval、metadata filter。
- 工具边界：internal tool service、stdio MCP Server、idempotency、audit log。
- 前端：Next.js 16、React 19、TypeScript、TailwindCSS。
- 测试与交付：pytest、ruff、Next lint/build、JSONL eval dataset、Markdown/JSON report。

## 技术难点

### 1. 让 Agent 可执行但不越权

难点不是“让模型给建议”，而是让建议进入受控业务流程。系统把 LLM 限制在理解和表达层，所有事实、政策、风险、审批和工具执行都由 deterministic service 决定。用户输入“跳过审批、直接退款”会被标记为 blocked / critical，不能降低风险或绕过审批。

### 2. 高风险动作的审批与幂等

退款必须有 matching approved approval request；高额 coupon 需要审批；工具执行还要校验 action plan、approval、order_no、amount、currency、policy evidence 和 execution_status。所有写接口都要求 `Idempotency-Key`，同 key 同 body 返回重放结果，同 key 不同 body 返回冲突，避免重复退款或重复发券。

### 3. Grounded RAG，而不是无依据回复

政策检索先按 status、生效期、category、aftersales_type、intent 过滤，再做向量排序。无有效政策时返回 empty hits，不编造依据。Agent 的 recommendation 必须引用 active policy evidence，否则转人工或要求补充信息。

### 4. MCP 只是适配层

MCP wrapper 不复制业务规则、不直接写 ORM、不自行判断审批，只负责参数校验、短生命周期 DB session、调用 internal service 和安全错误映射。这保证 HTTP 工具 API 与 MCP 工具行为一致。

### 5. 可复现评测

评测默认 `LLM_PROVIDER=disabled`，不依赖真实 DeepSeek，不产生网络成本。报告保留失败案例，避免为了求职展示美化指标。Evaluation Dashboard 只读取保存报告，未运行评测时不展示假数字。

## 面试讲解重点

1. 这个项目不是聊天 UI，而是受控业务 Agent。
2. LLM 不直接执行动作，所有写操作都有 service、审批、幂等和 audit 约束。
3. RAG 检索结果必须有政策 ID 和 chunk ID，空结果不编造依据。
4. 前端展示完整业务链路：Preview -> Action Plan -> Approval -> Mock Tool -> Audit -> Evaluation。
5. 当前指标来自真实本地评测报告，失败案例也被保留。

## 可诚实声明的指标

这些指标来自 `eval/reports/MVP_REPORT.md`，不要脱离报告单独夸大：

- 固定评测案例数：100。
- Task Success Rate：94.00%。
- Unsafe Action Block Rate：100.00%。
- Approval Enforcement Rate：100.00%。
- Idempotency Protection Rate：100.00%。
- Trace Completeness：100.00%。

## 不应声称的内容

- 不要说接入了真实支付或真实退款。
- 不要说 Agent 自动完成售后闭环。
- 不要说生产级认证、多租户或 SSO 已完成。
- 不要说真实 DeepSeek 指标已评测，除非后续单独运行并保存真实 provider 报告。
- 不要说 MCP 会被 Agent 自动调用；当前是本地 stdio 工具 wrapper。
