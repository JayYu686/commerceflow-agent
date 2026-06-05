# CommerceFlow Agent 系统架构设计

> 文档状态：MVP 技术基线  
> 原则：业务闭环优先、受控执行优先、可评测优先  
> 最后更新：2026-05-28

## 1. 架构目标

本系统实现“可执行但可控”的电商售后 Agent。架构必须同时满足：

1. **事实可追溯**：所有业务判断基于订单/物流工具结果和政策检索依据；
2. **动作可控制**：退款与高额赔付不能由 LLM 直接执行；
3. **流程可恢复**：Agent run 支持审批暂停、恢复和失败重试；
4. **效果可评测**：每一步工具调用、引用与动作结果可被自动评价；
5. **工程可交付**：本地 Docker Compose 可启动，面试可现场演示。

## 2. 固定技术决策

| 层次 | MVP 技术选择 | 决策理由 |
|---|---|---|
| Web 前端 | Next.js + TypeScript + TailwindCSS | 快速产出专业控制台 |
| API 后端 | Python + FastAPI + Pydantic | 与 Agent 生态一致，便于服务化 |
| ORM / Migration | SQLAlchemy 2.x + Alembic | 规范数据层与迁移管理 |
| Agent 编排 | LangGraph | 明确状态机、checkpoint 与 HITL interrupt |
| LLM 接口 | OpenAI-compatible model adapter | 可替换不同模型供应商 |
| 知识检索 | PostgreSQL + pgvector | 与业务库统一部署，支持检索原型 |
| Cache / Run 协调 | Redis | 缓存、幂等辅助锁、实时状态/队列预留 |
| 工具协议 | MCP Python SDK | 标准化业务工具暴露与调用 |
| Trace | 自建审计表 + 可选 Langfuse/OpenTelemetry | MVP 可落地且可扩展 |
| 测试 | pytest + Playwright（可后置） | API/Agent 核心优先 |
| 部署 | Docker Compose | 一键演示与复现 |

**实施约束**：Codex 在脚手架阶段应核查当前稳定包版本并生成锁文件，不在文档中硬编码未经验证的精确版本号。

## 3. 总体逻辑架构

```text
┌───────────────────────────────────────────────────────────────┐
│                        Next.js Web Console                     │
│ Chat Intake │ Run Timeline │ Approval Inbox │ Eval Dashboard   │
└───────────────────────────────┬───────────────────────────────┘
                                │ HTTP / SSE or WebSocket
┌───────────────────────────────▼───────────────────────────────┐
│                         FastAPI API Server                     │
│ Auth-lite │ Cases │ Approvals │ Runs │ Eval │ Streaming        │
└─────────────┬──────────────────┬──────────────────┬──────────┘
              │                  │                  │
     ┌────────▼────────┐ ┌──────▼──────────┐ ┌─────▼───────────┐
     │ LangGraph Agent │ │ RAG Service      │ │ Audit / Trace   │
     │ State/Interrupt │ │ Policy Retrieve  │ │ Events/Metrics  │
     └────────┬────────┘ └──────┬──────────┘ └─────┬───────────┘
              │                  │                  │
     ┌────────▼──────────────────▼──────────────────▼───────────┐
     │                 PostgreSQL + pgvector / Redis             │
     └───────────────────────────┬───────────────────────────────┘
                                 │
     ┌───────────────────────────▼───────────────────────────────┐
     │                       MCP Tool Servers                    │
     │ order │ logistics │ refund │ coupon │ ticket │ analytics* │
     └───────────────────────────┬───────────────────────────────┘
                                 │
     ┌───────────────────────────▼───────────────────────────────┐
     │              Mock Commerce Business Services / DB          │
     └───────────────────────────────────────────────────────────┘

* analytics 为 V2。
```

## 4. 推荐仓库结构

```text
commerceflow-agent/
├── AGENTS.md
├── PRD.md
├── ARCHITECTURE.md
├── PLANS.md
├── EVALUATION_SPEC.md
├── README.md
├── .env.example
├── docker-compose.yml
├── apps/
│   └── web/                         # Next.js 控制台
├── services/
│   ├── api/                         # FastAPI 网关与业务接口
│   │   ├── app/
│   │   │   ├── api/
│   │   │   ├── core/
│   │   │   ├── db/
│   │   │   ├── models/
│   │   │   ├── schemas/
│   │   │   └── services/
│   │   ├── alembic/
│   │   └── tests/
│   └── agent/                       # LangGraph runtime
│       ├── app/
│       │   ├── graph/
│       │   ├── prompts/
│       │   ├── tools/
│       │   ├── rag/
│       │   ├── guardrails/
│       │   └── trace/
│       └── tests/
├── mcp_servers/
│   ├── order_logistics/
│   ├── aftersales/
│   └── ticketing/
├── data/
│   ├── policies/
│   ├── seed/
│   └── eval/
├── eval/
│   ├── runner/
│   └── reports/
├── scripts/
└── docs/
    ├── diagrams/
    └── demo/
```

**MVP 简化原则**：如果拆成多个服务会妨碍快速交付，`services/api` 与 `services/agent` 可先运行于同一个 FastAPI 应用进程；模块边界保留，部署边界后移。

## 5. 关键运行流程

### 5.1 售后请求 Agent Run

```text
POST /api/cases
  → 创建 case 与 agent_run
  → LangGraph 开始运行
  → parse_request：意图/实体提取
  → validate_context：订单号是否充足
  → call MCP order_query + logistics_query
  → retrieve_policy：RAG 获取适用条款
  → decide_action：输出受 schema 约束的计划
  → risk_gate：
      Low/Allowed → execute_action
      High        → interrupt 并写入 approval_request
  → approved 时 resume → call refund/coupon/ticket MCP tools
  → generate_response
  → persist trace + result
```

### 5.2 审批恢复

```text
Agent 状态 = WAITING_APPROVAL
Reviewer 通过 UI 提交 APPROVE / REJECT + comment
FastAPI 校验 reviewer 与审批状态
写入 approval_decision 和 audit_event
使用已保存 thread/run 标识恢复 LangGraph
审批通过：执行唯一且预先展示的动作
审批拒绝：不得调用写工具，生成拒绝/升级回复
```

## 6. LangGraph 状态机设计

### 6.1 AgentState 建议字段

| 字段 | 类型 | 用途 |
|---|---|---|
| `run_id` | UUID | 追踪单次执行 |
| `case_id` | UUID | 所属售后案例 |
| `messages` | list | 会话消息 |
| `intent` | enum/null | 请求类型 |
| `entities` | object | 订单号、原因、期望动作等 |
| `order_snapshot` | object/null | 工具查询结果快照 |
| `logistics_snapshot` | object/null | 工具查询结果快照 |
| `policy_hits` | list | 条款、版本、score、来源 |
| `proposed_action` | object/null | 模型提出的结构化动作 |
| `risk_level` | enum/null | Low/Medium/High/Critical |
| `approval_id` | UUID/null | 等待审批时关联 |
| `tool_results` | list | 已调用工具记录 |
| `final_response` | string/null | 面向用户的回复 |
| `errors` | list | 可恢复/不可恢复异常 |
| `status` | enum | RUNNING/WAITING_APPROVAL/COMPLETED/FAILED |

### 6.2 节点与边

| 节点 | 输入 | 输出 | 失败处理 |
|---|---|---|---|
| `parse_request` | messages | intent/entities | 无订单号则进入 ask_for_info |
| `query_business_facts` | entities | order/logistics snapshot | 工具失败重试一次，再转人工 |
| `retrieve_policy` | intent/facts | policy_hits | 无高可信依据则禁止写动作 |
| `propose_action` | facts/policy | proposed_action | 只接受 schema 合法结果 |
| `risk_gate` | action | risk_level/approval | 高风险 interrupt |
| `execute_action` | approved action | tool_results | 依赖幂等键，失败可重试 |
| `respond` | all state | final_response | 不暴露内部敏感字段 |
| `record_outcome` | all state | metrics/audit | 审计写入不可由模型控制 |

## 7. 工具与 MCP 边界

### 7.1 原则

- LLM 不得持有数据库写权限；
- MCP 工具是可执行业务能力的唯一入口；
- 工具输入必须经过 Pydantic/JSON schema 校验；
- 工具输出是业务事实来源，必须写入 audit event；
- 写工具必须支持 `idempotency_key`；
- 工具本身再次校验权限与业务约束，不能只信任 Agent 的决策。

### 7.2 MVP Tools

| Tool | 输入摘要 | 输出摘要 | 风险 |
|---|---|---|---:|
| `order_query` | `order_no` | 订单、商品、金额、状态、售后状态 | Low |
| `logistics_query` | `order_no` | 轨迹、签收、延误天数 | Low |
| `policy_search` | intent/category/facts | 政策条款与版本 | Low |
| `ticket_create` | case/action/summary | ticket_id/status | Low |
| `coupon_issue` | order_no/amount/reason/idempotency_key | coupon_record | Medium/High |
| `refund_apply` | order_no/amount/reason/approval_id/idempotency_key | refund_record | High |

### 7.3 写操作二次防线

`refund_apply` 至少校验：

1. `approval_id` 存在且状态为 `APPROVED`；
2. 审批对应 action、金额、order_no 与调用参数完全一致；
3. 该订单没有成功退款，或当前请求使用相同幂等键返回既有结果；
4. 金额不超过已支付可退金额；
5. 操作写入审计记录。

## 8. 数据模型草案

### 8.1 业务表

| 表 | 关键字段 |
|---|---|
| `customers` | id, name, tier, risk_flag |
| `products` | id, sku, name, category, aftersales_type |
| `orders` | id, order_no(unique), customer_id, paid_amount, status, paid_at, delivered_at |
| `order_items` | id, order_id, product_id, quantity, unit_price |
| `shipments` | id, order_id, status, carrier, promised_at, delivered_at |
| `shipment_events` | id, shipment_id, event_type, occurred_at, description |
| `refunds` | id, order_id, amount, reason, status, idempotency_key(unique), approval_id |
| `coupons_issued` | id, order_id, amount, reason, idempotency_key(unique) |
| `tickets` | id, case_id, order_id, category, status, resolution |

### 8.2 Agent / 审批 / 检索表

| 表 | 关键字段 |
|---|---|
| `cases` | id, user_message, order_no, status, created_at |
| `agent_runs` | id, case_id, thread_id, status, model_name, started_at, finished_at |
| `tool_calls` | id, run_id, tool_name, request_json, response_json, risk_level, latency_ms, success |
| `approval_requests` | id, run_id, action_json, risk_level, status, requested_at |
| `approval_decisions` | id, approval_id, reviewer, decision, comment, decided_at |
| `audit_events` | id, run_id, event_type, payload_json, created_at |
| `policy_documents` | id, title, version, effective_from, status, category |
| `policy_chunks` | id, document_id, content, embedding, metadata_json |

## 9. API 接口草案

### 9.1 用户/演示接口

| Method | Path | 用途 |
|---|---|---|
| POST | `/api/cases` | 创建售后请求并启动 run |
| GET | `/api/cases/{case_id}` | 查看 case 状态 |
| GET | `/api/runs/{run_id}/timeline` | 查看执行时间线 |
| GET | `/api/runs/{run_id}/stream` | 获取运行事件流 |
| POST | `/api/cases/{case_id}/messages` | 补充订单号或信息 |

### 9.2 审批与结果

| Method | Path | 用途 |
|---|---|---|
| GET | `/api/approvals?status=pending` | 待审批列表 |
| POST | `/api/approvals/{approval_id}/decision` | 批准或拒绝 |
| GET | `/api/tickets/{ticket_id}` | 查看工单 |
| GET | `/api/refunds/{refund_id}` | 查看退款记录 |

### 9.3 管理/评测

| Method | Path | 用途 |
|---|---|---|
| POST | `/api/evaluations/runs` | 启动评测 |
| GET | `/api/evaluations/{id}` | 获取评测报告 |
| POST | `/api/admin/seed/reset` | 仅开发环境重置 seed |

## 10. RAG 设计

### 10.1 文档模型

每条政策必须包含：

- `policy_id`、标题、版本、生效日期、状态（active/deprecated）；
- 适用品类、适用意图、条件、动作限制；
- 明确的政策正文；
- 是否允许自动补偿、是否必须人工审批。

### 10.2 Ingestion

1. 加载 Markdown/JSON 政策文档；
2. 按条款语义切分，避免把适用条件与动作上限分开；
3. 保存 metadata：category、intent、version、effective_from、active；
4. 生成 embedding 并入库；
5. 提供可重入的 ingestion 脚本与测试数据。

### 10.3 Retrieval

- 基于意图、品类、事件事实构建 query；
- metadata 优先过滤 active 且当前生效版本；
- 向量召回 top-k；
- MVP 可实现轻量重排或结构化筛选；
- 写动作只有在命中有效且足够可信的政策时才可提出；
- timeline 展示命中的条款、版本与 score。

## 11. 安全、权限与审计

### 11.1 MVP 身份模型

MVP 可使用简化演示身份：

- `demo_customer`
- `demo_agent`
- `demo_reviewer`

写操作 API 仍必须检查 reviewer header/session 角色，不因为是 Demo 就省略流程。

### 11.2 安全控制

| 风险 | 控制 |
|---|---|
| 重复退款 | DB unique constraint + idempotency_key + tool 校验 |
| 越权退款 | LangGraph interrupt + approval record + tool 二次校验 |
| Prompt Injection | 用户输入永远不改变系统政策和工具权限；安全案例评测 |
| 伪造事实 | 决策只依赖工具 snapshot 和有效 policy hits |
| SQL 危险写入 | MVP 不提供任意 SQL；V2 analytics 只读 allowlist |
| 敏感信息泄漏 | timeline 脱敏，审计表保存必要字段 |
| 工具失败 | 重试次数有限，失败时升级人工而非猜测成功 |

## 12. 可观测性与评测挂钩

每一次 run 至少记录：

- 输入意图、实体识别结果；
- 检索 hits、政策版本和得分；
- 每次 MCP tool 调用参数摘要、结果、耗时、成功状态；
- 风险判定及审批动作；
- 最终业务结果；
- LLM 模型名、token/cost（API 可提供时）；
- 评测标注对比结果。

## 13. 部署拓扑（MVP）

```text
docker compose
├── web            # Next.js
├── api            # FastAPI + Agent runtime
├── postgres       # PostgreSQL + pgvector
├── redis          # cache / state
└── optional-trace # Langfuse 等后置启用
```

MCP 工具服务在 MVP 可以作为独立 Python 进程或由 compose 服务承载；不能用“前端伪造 tool call”替代真实服务调用。

## 14. 重要架构决策记录（ADR 摘要）

| 决策 | 选择 | 不选择什么 | 原因 |
|---|---|---|---|
| Agent 控制方式 | 显式状态机 | 自由多 Agent 群聊 | 业务写动作需可预测、可审计 |
| 数据 | 模拟业务库 | 真实电商 API | 可公开、可复现、无隐私风险 |
| 写动作 | MCP 工具 + 审批 | LLM 直接写 DB | 权限清晰、可安全评测 |
| 检索库 | pgvector | 单独引入复杂搜索集群 | MVP 快速交付 |
| 初期部署 | Compose | Kubernetes | 简历 MVP 不需要过度工程化 |
