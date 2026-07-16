CommerceFlow Agent v1.1.2 Windows 体验说明
==========================================

这是一个求职演示用途的本地 Mock 系统，不会调用真实支付、退款、优惠券或客服系统。

运行要求
--------
1. Windows 10/11 x64。
2. 已安装并启动 Docker Desktop。
3. 端口 3000 和 8000 未被其他程序占用。
4. 首次启动需要联网从 GitHub Container Registry 拉取镜像。

快速开始
--------
1. 双击 CommerceFlowAgent.exe。
2. 选择“启动系统并打开浏览器”。
3. 等待浏览器打开 http://localhost:3000。

命令行
------
CommerceFlowAgent.exe start
CommerceFlowAgent.exe start --observability
CommerceFlowAgent.exe status
CommerceFlowAgent.exe stop
CommerceFlowAgent.exe reset

stop 会停止容器但保留本地演示数据。
reset 会要求二次确认，并删除本地演示数据后重新初始化。
start --observability 会额外启动 OpenTelemetry Collector 和 Jaeger，访问 http://localhost:16686 查看运行链路。

安全说明
--------
- 默认关闭真实 LLM。
- 退款、优惠券和工单均为本地 Mock 记录。
- 高风险退款仍需在控制台完成人工审批。
- 本程序未使用商业代码签名证书，Windows 可能显示 SmartScreen 提示。
