import { Badge } from "../../components/console/Badge";
import { Panel } from "../../components/console/Panel";

export default function EvaluationPage() {
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header className="border-b border-line pb-6">
        <p className="text-sm font-semibold uppercase tracking-wide text-signal">Phase 5C</p>
        <h2 className="mt-1 text-3xl font-semibold tracking-tight">评测看板</h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
          本页是 Phase 5C 占位。当前阶段不实现真实评测运行器，也不展示未验证指标。
        </p>
      </header>
      <Panel title="即将实现" eyebrow="评测指标占位">
        <div className="flex flex-wrap gap-2">
          <Badge tone="info">测试案例</Badge>
          <Badge tone="info">任务成功率</Badge>
          <Badge tone="info">政策依据命中率</Badge>
          <Badge tone="info">越权请求拦截率</Badge>
          <Badge tone="info">延迟与成本</Badge>
        </div>
        <p className="mt-4 text-sm leading-6 text-slate-600">
          这些指标必须来自可复现评测命令和保存的报告，不能手工编造或只依赖演示印象。
        </p>
      </Panel>
    </div>
  );
}
