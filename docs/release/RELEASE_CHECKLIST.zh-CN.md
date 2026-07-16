# CommerceFlow Agent v1.1.2 发布清单

本清单用于维护者发布 GitHub Release。`v1.1.2` tag 只有在后端、前端 E2E、镜像和 Windows 启动器构建全部成功后才会自动发布为 Latest；`v1.0.0` 保留为可回退版本。

## 1. 发布前自动验证

- `main` 工作区干净，后端全量 pytest、Ruff、`pip check` 全部通过。
- 前端 lint、production build、Playwright Chromium E2E 全部通过。
- Go Windows 启动器测试通过。
- Alembic 位于 `202607160001 (head)`，官方 LangGraph checkpoint 四张表已完成 setup。
- v2 确定性评测实际生成 JSON/Markdown 报告，120 条案例和失败记录均保留。
- `.env`、API Key、Token、连接串、prompt 和本地绝对路径未进入 Git diff。
- 依赖范围不包含 Redis、OpenAI Agents SDK、CrewAI 或 AutoGen。

## 2. Docker 冷启动验收

在全新 named volume 上验证：

1. 默认仅启动 PostgreSQL、API 和 Web；
2. API 自动完成 Alembic、checkpoint setup 和幂等 demo bootstrap；
3. `/health`、Workbench、审批、执行确认、stdio MCP、Mock Result 和 Audit 可用；
4. API/Web 重启后暂停中的工作流可恢复；
5. 审批通过不会自动执行，拒绝后不能执行；
6. `--profile observability` 能启动 Collector/Jaeger，页面可显示 trace_id；
7. stop/start 保留数据，只有显式 reset 才删除演示数据。

## 3. 触发 Release

```powershell
git tag -a v1.1.2 -m "CommerceFlow Agent v1.1.2"
git push origin v1.1.2
```

Tag 会触发 `.github/workflows/release.yml`：

1. 执行后端、前端、E2E 和启动器验证；
2. 构建并推送 API/Web 镜像到 GHCR；
3. 构建 Windows ZIP 和 SHA-256；
4. 自动创建正式 Release 并标记为 Latest。

## 4. 人工发布门槛

- 将 `commerceflow-agent-api` 和 `commerceflow-agent-web` 两个 GHCR package 设置为 Public。
- 在未登录 GitHub 的环境中匿名拉取 `v1.1.2` 镜像。
- 在仅安装 Docker Desktop 的干净 Windows x64 环境下载 ZIP 并校验 SHA-256。
- 验证启动器 `start`、`start --observability`、`status`、`stop`、`reset`。
- 完成质量退款：创建计划 -> 审批 -> 等待执行确认 -> stdio MCP -> Mock Result -> Audit/trace。
- 验证拒绝审批、MCP 不可用和同 key replay 的安全行为。
- 确认 Windows SmartScreen 被如实描述为“当前未进行商业代码签名”。
- 复核 npm audit 中当前无上游修复的 Next.js/PostCSS moderate advisory，并在有修复版本后升级。

以上人工门槛应在创建 tag 前完成；CI 任一任务失败时不会创建 Release。

## 5. 回滚

如果任一门槛失败：

- 保持失败 tag 对应的 Release 不发布；
- 不把失败镜像标记为稳定版本；
- 回退到已发布的 `v1.0.0`；
- 修复后创建新的语义版本 tag，不覆盖已公开资产。
