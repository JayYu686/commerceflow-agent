# CommerceFlow Agent Starter Documentation Bundle

该目录包含一套可以直接放入项目根目录、交给 Codex 读取的设计与执行文档：

- `PRD.md`：产品目标、MVP 范围、核心流程与验收标准
- `ARCHITECTURE.md`：系统架构、状态机、工具、数据表与安全边界
- `AGENTS.md`：Codex 必须遵守的仓库级开发规则
- `PLANS.md`：P0-P6 实施路线、阶段验收与任务计划模板
- `EVALUATION_SPEC.md`：测试集、指标、安全测试与报告规范
- `CODEX_BOOTSTRAP_PROMPT.md`：第一次与后续每阶段可粘贴给 Codex 的提示词

推荐开始方式：

1. 将这些文档复制到新仓库根目录。
2. 在 Codex CLI 中进入 Plan 模式。
3. 粘贴 `CODEX_BOOTSTRAP_PROMPT.md` 中的 Prompt A。
4. 审查其方案后再批准实施 Phase 0。
