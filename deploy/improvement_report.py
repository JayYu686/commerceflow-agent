"""Render the budgeted experiment without altering original runs or golden labels."""

import hashlib
import json
from collections import Counter
from pathlib import Path

from evaluation_report import table_row

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "eval/reports/v2"


def main():
    specs = {
        "deepseek-before-full": ("改进前完整集", 450, "test.jsonl"),
        "deepseek-after-full": ("改进后回归集", 150, "test.jsonl"),
        "deepseek-failure-regression": (
            "已知失败专项回归",
            20,
            "failure-regression.jsonl",
        ),
        "fixed-current": ("当前固定工作流", 150, "test.jsonl"),
        "deepseek-before-dev": ("改进前开发集", 50, "dev.jsonl"),
        "deepseek-final-dev": ("最终版本开发集", 50, "dev.jsonl"),
        "deepseek-after-dev": ("中间候选开发集", 50, "dev.jsonl"),
        "deepseek-before-multiturn": ("改进前多轮验收", 12, "multiturn.jsonl"),
        "deepseek-final-multiturn": ("最终版本多轮验收", 12, "multiturn.jsonl"),
        "deepseek-after-multiturn": ("中间候选多轮验收", 12, "multiturn.jsonl"),
    }
    reports = {}
    for name, (_, count, dataset) in specs.items():
        report = json.loads((REPORTS / (name + ".json")).read_text(encoding="utf-8"))
        assert report.get("finished_at"), f"Incomplete run: {name}"
        rows = report["results"]
        assert len(rows) == count, f"Wrong result count: {name}"
        assert len({(r.get("repeat", 1), r["scenario_id"]) for r in rows}) == count
        raw = (ROOT / "data/eval/v2" / dataset).read_bytes().replace(b"\r\n", b"\n")
        # Raw-file hashes include Windows line endings. Reconstruct either exact
        # source byte sequence; no JSON contents or labels may differ.
        source_hashes = {
            hashlib.sha256(raw).hexdigest(),
            hashlib.sha256(raw.replace(b"\n", b"\r\n")).hexdigest(),
        }
        assert report["dataset_sha256"] in source_hashes
        reports[name] = report
    budget = json.loads(
        (REPORTS / "budget-improvement.json").read_text(encoding="utf-8")
    )
    lines = [
        "# DeepSeek 完整评测与改进实测",
        "",
        "本报告由 `python deploy/improvement_report.py` 从保留全部失败的原始结果生成。",
        "旧版Qwen与30条DeepSeek成绩仍保留在 [原始报告](REPORT.md)，不拼接为新的模型成绩。",
        "",
        "## 实验与边界",
        "",
        "- 用户批准新增10–15元；本轮将本地累计准入上限降为15.49元，原项目25/30元限制未提高。",
        "- 使用DeepSeek-flash非思考模式，temperature=0.7、top_p=0.8、max_tokens=1024；完整集并发4，开发集/多轮并发2。没有训练或微调模型权重。",
        "- 完整测试集仍为15情景族、每族10个合成变体。改进前跑三次；开发/多轮验证及中间候选复测后，剩余预算不足两轮完整回归，因此改进后跑一轮150条，并对基线的4个失败各重复5次。专项回归不并入完整集分母。",
        "- 改进只调整调查提示词：区分用户缺信息与业务资格拒绝；明确商品无需重复追问；拒绝绕过审批的指令同时继续处理合法诉求；换目标重新取证。",
        "- 首个候选验证期间，基线第二轮发现退款诉求被改成物流补偿。因此增加保持用户处理类型的约束，再完整验证最终候选；中间候选的结果和费用同样保留。",
        "- 已查看旧测试集失败，因此改进后成绩是回归结果，不能称为未见测试集泛化成绩。原始标签和评分规则没有改动。",
        "- 12条多轮验收在改进前冻结，包含6种交互各2个变体；是补充合成验收，不是独立大规模真实客服测试。",
        "- 政策仅两项，Recall@5只验证接入。工具参数只检查订单号/商品行ID，引用只检查实际方案的政策版本、哈希和原文。",
        "- 运行共享本地CPU和远程数据库且部分时段重叠，延迟不可作为隔离的模型速度对比。Qwen没有重新运行，不能声称其效果得到提升。",
        "- 数据哈希记录运行时原始字节。专项子集首次在Windows写出CRLF，Git按仓库规则保存LF；生成器验证这两种可重建字节形式，JSON内容及标签必须完全相同。",
        "",
        "## 完整集与开发集",
        "",
        "| 配置 | 任务成功 | 关键工具参数 | 政策 Recall@5 | 方案引用 | 平均/P95秒 | API费用上界/元 |",
        "|---|---|---|---|---|---|---|",
    ]
    for name in (n for n in specs if "multiturn" not in n):
        label = specs[name][0]
        rows = reports[name]["results"]
        if name.endswith("-full"):
            for repeat in sorted({r["repeat"] for r in rows}):
                lines.append(
                    table_row(
                        f"{label} 第{repeat}轮",
                        [r for r in rows if r["repeat"] == repeat],
                    )
                )
        lines.append(table_row(label + " 合计", rows))
    lines += [
        "",
        "## 多轮验收",
        "",
        "| 配置 | 成功 | API费用上界/元 |",
        "|---|---|---|",
    ]
    for name in (n for n in specs if "multiturn" in n):
        rows = reports[name]["results"]
        lines.append(
            f"| {specs[name][0]} | {sum(r['passed'] for r in rows)}/{len(rows)} | {sum(r['cost_upper_yuan'] for r in rows):.6f} |"
        )
    lines += [
        "",
        "这些案例实际调用模型与MCP；缺订单/缺故障/商品不明时先澄清，再审核、确认和执行。",
        "换订单或商品案例先批准旧方案，再验证旧批准失效、新方案未经批准不能执行，最终只修改新目标商品。",
        "补偿案例完成后再次申请，检查权益仍只有一条。安全断言是确定性断言，模型回复本身不算业务凭证。",
        "",
        "## 各情景与失败",
        "",
        "| 情景族 | 改进前 | 改进后 |",
        "|---|---|---|",
    ]
    before = reports["deepseek-before-full"]["results"]
    after = reports["deepseek-after-full"]["results"]
    for family in sorted({r["family"] for r in before}):
        values = []
        for rows in [before, after]:
            group = [r for r in rows if r["family"] == family]
            values.append(f"{sum(r['passed'] for r in group)}/{len(group)}")
        lines.append(f"| {family} | {' | '.join(values)} |")
    for name, report in reports.items():
        failed = [r for r in report["results"] if not r["passed"]]
        reasons = Counter(
            r["failure"] or f"终态{r.get('observed')}，预期{r.get('expected')}"
            for r in failed
        )
        lines += [
            "",
            f"### {specs[name][0]}",
            "",
            f"失败 {len(failed)}/{len(report['results'])}；分类：{dict(reasons)}",
            "",
        ]
        for r in failed:
            lines.append(
                f"- `{r['scenario_id']}` 第{r.get('repeat', 1)}轮，案件 `{r['case_id']}`：{r['failure'] or r.get('observed')}"
            )
        models = sorted({m for r in report["results"] for m in r["actual_models"]})
        lines += [
            "",
            f"[完整原始事件]({name}.json)；代码 `{report['git_commit']}`；API返回模型：{models or ['无模型']}。",
            f"开始 {report['started_at']}；结束 {report['finished_at']}；数据SHA-256 `{report['dataset_sha256']}`。",
        ]
    lines += [
        "",
        "## 费用与结论",
        "",
        f"项目累计保守记账 **{budget['committed_and_reserved_yuan']:.6f} 元**；本轮新增 **{budget['incremental_yuan']:.6f} 元**。",
        f"全部项目调用 {budget['calls']} 次，未知用量 {budget['unknown_usage_calls']} 次；[账本快照](budget-improvement.json)。",
        "按已核实的最高输入2元/百万、输出8元/百万计费，缓存也按最高价估算；不是供应商发票金额或账号级消费限制。",
        "完整评测比此前30条子集更充分，但重复运行不是新的独立样本。若改进幅度很小，不应包装成显著提升；",
        "求职展示的主要证据是受控工具调用、授权绑定、真实业务凭证和恢复实验，模型成绩须同时说明数据范围。",
        "",
    ]
    (REPORTS / "IMPROVEMENT.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
