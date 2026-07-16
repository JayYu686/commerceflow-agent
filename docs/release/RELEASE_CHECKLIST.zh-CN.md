# CommerceFlow Agent v1.0.0 发布清单

本清单用于维护者发布 GitHub Release。发布 workflow 会先创建 Draft Release，不会自动绕过人工验收。

## 1. 发布前

- `main` 工作区干净，后端 pytest/Ruff、前端 lint/build、Go test 全部通过。
- API/Web Docker 镜像可以从空 volume 自动执行 migration 和 demo bootstrap。
- Windows 启动器的 `start`、`status`、`stop`、`reset` 已在 Windows x64 验证。
- README 中的版本号、评测指标、License 和下载说明准确。
- `.env`、API Key、Token、连接串和本地绝对路径未进入 Git diff。

## 2. 触发 Draft Release

```powershell
git tag -a v1.0.0 -m "CommerceFlow Agent v1.0.0"
git push origin v1.0.0
```

Tag 会触发 `.github/workflows/release.yml`：

1. 执行后端、前端和启动器验证；
2. 推送 API/Web 镜像到 GHCR；
3. 构建 Windows ZIP 和 SHA-256；
4. 创建 Draft Release。

## 3. 人工发布门槛

- 在 GitHub Packages 中将 `commerceflow-agent-api` 和 `commerceflow-agent-web` 设置为 Public。
- 在未登录 GitHub 的环境中执行匿名 `docker pull`。
- 在仅安装 Docker Desktop 的干净 Windows x64 环境中下载 ZIP 并校验 SHA-256。
- 完成质量退款、审批、Mock 工具、审计时间线的完整演示。
- 验证 stop/start 保留数据，reset 明确确认后才清理数据。
- 确认 Windows SmartScreen 未被描述为商业代码签名错误，README 已说明当前未签名。

全部通过后，才在 GitHub 将 Draft Release 发布为正式版本。

## 4. 回滚

如果任一门槛失败：

- 保持 Release 为 Draft；
- 不把失败镜像标记为新的稳定版本；
- 修复后创建新的语义版本 tag，不覆盖已经公开的版本资产。
