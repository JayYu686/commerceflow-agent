# 给 Codex 的启动提示词与开发协作方式

> 用法：将本文件和五份根文档放入仓库根目录。第一轮建议在 Codex CLI 中进入 Plan 模式后粘贴“Prompt A”。Codex 读完、输出方案并经你确认后，才粘贴“Prompt B”实施 Phase 0。

## 0. 在 Codex 开始前你需要做什么

1. 新建一个空仓库目录，例如 `commerceflow-agent`。
2. 将以下文件放到根目录：
   - `PRD.md`
   - `ARCHITECTURE.md`
   - `AGENTS.md`
   - `PLANS.md`
   - `EVALUATION_SPEC.md`
   - 本文件 `CODEX_BOOTSTRAP_PROMPT.md`
3. 初始化 Git：`git init`。
4. 在 Codex 中使用 Plan 模式进行第一次沟通。
5. 第一轮只规划，不要同意它一次性实现所有模块。

## Prompt A：第一次让 Codex 理解项目并制定完整方案

```text
你现在是本项目的资深技术负责人和实现工程师。当前目标不是立即大量写代码，而是先全面理解项目、提出一套可执行且不过度设计的实施方案。

请先严格按顺序阅读仓库根目录中的：
1. AGENTS.md
2. PRD.md
3. ARCHITECTURE.md
4. PLANS.md
5. EVALUATION_SPEC.md

项目是 CommerceFlow Agent：面向电商售后场景的可执行但可控的业务 Agent，用于展示 Agent 应用开发岗位所需的后端、RAG、LangGraph、MCP、审批、安全审计、评测和部署能力。

本轮任务仅做规划和必要的仓库检查，不要开始实现完整业务功能，不要创建大批样板代码。

请完成以下工作：
1. 检查当前仓库内容和本机可用工具链（Git、Python、Node、Docker 等），但不要执行破坏性操作。
2. 用自己的话总结产品目标、MVP 边界、三条最关键演示链路，以及十条不可破坏的安全不变量。
3. 审查文档方案是否存在冲突、过度设计、遗漏或技术风险，特别关注：
   - FastAPI / Next.js / PostgreSQL+pgvector / Redis / LangGraph / MCP / Docker Compose 的组合是否适合 MVP；
   - Agent graph、审批中断与恢复、退款幂等、政策版本检索、审计与评测是否能正确落地；
   - 哪些能力应该延后而不是进入 MVP。
4. 制定 P0-P6 的总体实施路线，为每阶段写明：
   - 交付结果；
   - 关键文件/目录；
   - 依赖与技术选型；
   - 测试与验收方式；
   - 风险与回滚策略；
   - 推荐 Git commit 划分。
5. 将 Phase 0 细化成第一个可实施的 Execution Plan，控制在一次可审查的小范围改动内。Phase 0 只应建立仓库、依赖服务、FastAPI health check、Next.js 起始页面、测试/格式化基线与 README 启动说明，不要提前实现订单、RAG 或 Agent。
6. 列出最多 5 个确实必须由我决定的问题；对于不影响开始开发的小问题，请给出合理默认选择，不要用问题阻塞规划。
7. 最终输出以下栏目：
   - Project Understanding
   - Safety Invariants
   - Architecture Review
   - P0-P6 Roadmap
   - Phase 0 Execution Plan
   - Decisions Needed From Me
   - Recommended First Implementation Prompt

除非我明确批准 Phase 0 实施，否则不要修改业务代码、不要生成未要求的依赖服务、不要写虚构评测结果。
```

## 你应如何审查 Codex 的第一次回复

你只需检查六件事：

- 它是否正确理解“不是聊天机器人，而是受控业务 Agent”；
- 它是否保留退款必须审批、写操作幂等、政策依据和审计；
- 它是否擅自把 P0 扩大成完整系统；
- 它是否给出了真实可运行的技术路径；
- 它是否解释了每阶段怎么测试；
- 它的问题是否真的必须回答。

如果回复合理，再让它把通过的计划写入仓库中的 `IMPLEMENTATION_PLAN.md`，或直接开始 Phase 0。

## Prompt B：批准后开始 Phase 0

```text
我已审阅并批准你提出的 Phase 0 Execution Plan。请继续遵守 AGENTS.md 和全部根文档。

本轮只实现 Phase 0，不实现订单、物流、RAG、Agent、MCP 或审批业务代码。目标是搭建一个可运行、可测试、可复现的工程基线。

请：
1. 在实施前再次给出本轮将新增/修改的文件列表和预计命令。
2. 初始化约定的项目骨架、FastAPI /health、Next.js 起始页面、PostgreSQL+pgvector 与 Redis 的 Docker Compose 配置、.env.example、.gitignore、最小测试与 README 启动说明。
3. 选择兼容且稳定的包版本，并生成/提交所需锁文件；不要硬编码任何密钥。
4. 运行能够在当前环境中执行的验证命令；如果 Docker 或依赖受限，明确说明未验证部分和原因。
5. 完成后输出：修改文件清单、启动方式、测试结果、已知问题、下一步 Phase 1 的最小任务建议。
6. 不要自行 git commit，先让我检查 diff。
```

## Prompt C：每个后续功能任务的标准模板

```text
请先阅读 AGENTS.md，并核对 PRD.md、ARCHITECTURE.md、PLANS.md、EVALUATION_SPEC.md 中与本任务相关的要求。

本轮只实现：<填写一个明确的小任务，例如“订单与物流只读查询 API + seed 数据 + 测试”>。

必须满足：
- Scope in: <列出这次要做的功能>
- Scope out: <列出明确不要做的功能>
- Safety invariants: <列出本任务触及的安全约束>
- Acceptance tests: <列出必须通过的成功/失败测试>
- Documentation update: <涉及契约变化时更新哪些文档>

执行方式：
1. 先检查现有实现并提出文件级计划。
2. 我确认或该计划与既定 Phase 完全一致后，再实施。
3. 只修改与任务直接相关的文件，避免无关重构。
4. 完成后运行测试并汇总 diff、测试结果、风险和下一任务。
5. 不要编造效果数据，不要绕过安全规则，不要自动提交密钥或破坏性更改。
```

## Prompt D：让 Codex 做代码审查而不是继续扩展功能

```text
本轮不新增功能。请作为严格 reviewer 审查当前 diff / 最近一次实现，重点检查：
1. 是否违反 AGENTS.md 的安全不变量；
2. 写操作是否存在绕过审批、重复执行、金额/订单不一致等问题；
3. API、schema、数据库约束、migration 与测试是否一致；
4. 是否出现硬编码密钥、未处理异常、过度复杂设计或无关改动；
5. 是否真的达到了本阶段验收标准。

请按严重等级输出问题，给出具体文件位置与修复建议；只有在我要求时再修改代码。
```

## 建议协作节奏

- 第一次：Prompt A，拿到整体方案；
- 审查方案：保留/修改关键决策；
- 第二次：Prompt B，只做 P0；
- 后续：用 Prompt C 每次推进一个小任务；
- 每完成一个阶段：用 Prompt D 审代码、安全与测试；
- 评测阶段：将实际结果写入报告后再生成简历描述。

## 关键提醒

- Codex 写得快不等于设计正确；每次关注 diff 和测试。
- “完成了”必须对应可运行命令或测试证据。
- 你需要能在面试中解释：Graph 状态流转、MCP tool 边界、RAG 依据、审批中断恢复、退款幂等、评测指标。
