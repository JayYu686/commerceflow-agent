# v2 部署与验证

## 运行边界

应用服务：API 8000、commerce 8001、web 3000；开发数据库 55432；Qwen 推理 18080。
Compose 默认只向本机发布 web 和数据库，commerce 和执行写接口留在内部网络。
旧版数据库及 volume 不参与初始化。`down` 停止容器；不要加 `-v`，除非明确要删除 v2 演示数据。

`python deploy/configure.py` 生成 `.env.v2`，不会覆盖现有文件。后端启动缺少密码时无法登录，缺少服务 token 时无法调用业务工具。

## Qwen 与共享 GPU

使用 Qwen3-8B 权重 revision `b968826d9c46dd6066d109eabc6255188de91218`。
当前验证环境使用 vLLM `0.8.5.post1+cu118`、PyTorch `2.6.0+cu118`、Python 3.11，独立于应用 Python 3.13 环境。
主机驱动不升级。最多允许使用4张空闲3090；本项目默认只使用1张，8K上下文，最多2个同时生成序列。

`deploy/serve_qwen.py` 在启动前检查指定 GPU 的显存及计算进程，有占用则停止启动；不杀其他进程。
部署目录需包含独立 `.venv`、只允许本人读取的 `credentials.json`（其中 `model_key` 与应用配置一致）。

```bash
python deploy/serve_qwen.py --runtime /your/commerceflow-runtime --model /your/Qwen3-8B --gpu 0
```

模型服务绑定服务器127.0.0.1，开启 API key 验证。原生本地演示可用 SSH：

```bash
ssh -N -L 18080:127.0.0.1:18080 your-server
```

检查个人 SSH 配置中的 RemoteForward，避免无关转发。需要忽略个人配置时用 `-F` 指定空配置并显式提供用户名和身份文件。**不要在需要转发的连接上使用 `ClearAllForwardings=yes`，它也会清掉命令行的 `-L`。**

演示/评测结束后立即停止独立推理服务，避免模型空闲时仍占用显存：

```bash
python deploy/stop_qwen.py --runtime /your/commerceflow-runtime
```

该命令核对 PID 对应的运行目录和独立进程组，只停止本项目服务及其子进程。若出现 D/Z 状态，不能声称显存已释放，需要由服务器维护者排查驱动；脚本不会重置 GPU 或重启服务器。

## 本地原生与完整 Compose

原生应用使用 `CF_MODEL_URL`；完整 Compose 使用 `CF_CONTAINER_MODEL_URL`。容器中的127.0.0.1不是宿主机，部署时必须提供容器实际可达且经过鉴权的模型地址。
宿主机仅绑定127.0.0.1的SSH隧道，不能假设所有Docker网络都可以访问；这种开发连接按 README 的“原生应用开发”方式运行。
也可以显式选择 DeepSeek，用服务器端密钥连接其官方 API；不会自动从 Qwen 切到 DeepSeek。

网页通过 Next.js 服务端代理 `/api`；公网部署应额外配置 HTTPS 并设置 `CF_COOKIE_SECURE=true`。本次交付不包含公网托管及域名。

## 无管理员权限的 PostgreSQL 测试环境

为便于在共享 Linux 服务器上验证真实数据库，提供用户目录内启动方式。它不修改系统服务、Docker权限或其他人的数据库。

```bash
conda create -y -p /your/commerceflow-runtime/postgres --override-channels -c conda-forge postgresql=16 pgvector=0.7.4
python deploy/user_postgres.py /your/commerceflow-runtime
```

该目录的 `credentials.json` 另外包含 `agent_password` 和 `commerce_password`，与 `.env.v2` 一致。脚本创建 `cf_agent_v2`、`cf_commerce_v2`、`cf_agent_test`、`cf_commerce_test`；仅监听127.0.0.1:55432，目录权限设为700。开发机通过单独 SSH 隧道访问。

本次真实数据库验证环境为 PostgreSQL16.15 + pgvector0.7.4。容器构建和 CI 另外使用 pgvector 的 PostgreSQL16 镜像。

## 集成测试库

管理员创建 `cf_agent_test OWNER cf_agent` 和 `cf_commerce_test OWNER cf_commerce`；取消 PUBLIC 的 CONNECT 权限，仅允许对应角色连接；在 agent 测试库安装 `vector` 扩展。
具体 SQL 也在 GitHub Actions 的初始化步骤中。

测试自动把演示数据库 URL 的末尾数据库名替换成对应 `_test` 名称，若名称不符合则拒绝清空。测试只清空专用测试库；不能将演示库别名为 `_test`。

## 启停与日志

`python deploy/local.py start` 为原生演示启动 API、commerce、worker、Next.js，并把 PID 写到 `data/local/processes.json`，日志在同目录。停止时按这些记录逐项核对进程，不使用按名字批量终止。

`python deploy/smoke.py` 调用真实模型完成 CF000001 的退款全链路。该命令会消耗该演示订单的退款权益；不是无副作用的健康检查。

浏览器端到端测试默认只检查登录页。显式设置 `CF_E2E_REAL_MODEL=1` 后，会用独立客服/审核员会话处理退款、补偿和重复申请并保留截图。默认消耗 CF000004 与 CF000002 的权益；复跑用 `CF_E2E_ORDER`、`CF_E2E_DELAY_ORDER` 指定尚未处理的同类订单，不清空账本。

`python deploy/verify_multiturn.py --order CF000010` 验证缺订单号的追问、补充信息后199元商品行方案，以及 SSE 的 Last-Event-ID 续接；它停在待审核，不执行退款。

DeepSeek预算账本位于应用数据库，跨重启保留；不要为重置评测而清空账本。预算只约束本项目的调用，不覆盖账号在其他程序的消费。
