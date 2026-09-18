"""Render completed, unmodified benchmark artifacts into a reproducible Markdown report."""

import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "eval/reports/v2"


def rate(values):
    values = [v for v in values if v is not None]
    return (
        f"{sum(values)}/{len(values)} ({sum(values) / len(values):.1%})"
        if values
        else "—"
    )


def table_row(name, rows):
    correct = sum(r["argument_correct"] for r in rows)
    total = sum(r["argument_total"] for r in rows)
    latency = sorted(r["latency_seconds"] for r in rows)
    args = f"{correct}/{total} ({correct / total:.1%})" if total else "—"
    return (
        f"| {name} | {rate([r['passed'] for r in rows])} | {args} | "
        f"{rate([r['policy_recall'] for r in rows])} | "
        f"{rate([r['plan_citation_valid'] for r in rows])} | "
        f"{statistics.mean(latency):.2f} / {latency[max(0, int(len(latency) * 0.95) - 1)]:.2f} | "
        f"{sum(r['cost_upper_yuan'] for r in rows):.6f} |"
    )


def main():
    reports = {
        name: json.loads((REPORTS / f"{name}.json").read_text(encoding="utf-8"))
        for name in ("qwen", "fixed", "deepseek")
    }
    dataset = (ROOT / "data/eval/v2/test.jsonl").read_bytes()
    sha = hashlib.sha256(dataset).hexdigest()
    expected_counts = {"qwen": 450, "fixed": 150, "deepseek": 30}
    for name, report in reports.items():
        assert report.get("finished_at"), f"{name} is incomplete"
        normalized = dataset.replace(b"\r\n", b"\n")
        assert report["dataset_sha256"] in {
            hashlib.sha256(normalized).hexdigest(),
            hashlib.sha256(normalized.replace(b"\n", b"\r\n")).hexdigest(),
        }, "Dataset content changed (only platform line endings may differ)"
        assert len(report["results"]) == expected_counts[name]
        assert (
            len({(r["repeat"], r["scenario_id"]) for r in report["results"]})
            == expected_counts[name]
        )
    qwen, fixed, deepseek = (
        reports[n]["results"] for n in ("qwen", "fixed", "deepseek")
    )
    lines = [
        "# CommerceFlow v2 真实模型评测",
        "",
        "本报告由 `python deploy/evaluation_report.py` 从完整原始结果生成。没有删除失败、重跑取最好成绩或沿用 v1 成绩。",
        "",
        "## 测试集与口径",
        "",
        "开发集50条、测试集150条，按业务情景族划分为5/15族，每族10个合成变体。组间没有同模板改写交叉；这仍是范围有限的合成集，不是150种独立业务规则或真实线上流量。",
        "",
        f"测试集 SHA-256：`{sha}`。",
        "",
        "- 任务成功：案件终态符合预先标签；成功业务还校验实际账本条数、问题商品退款额及另一商品未退款。退款由测试审核员显式授权，不让模型自审。异常计失败。",
        "- 关键工具参数：仅统计实际工具事件中的订单号、商品行ID是否符合目标；不包含全部JSON字段和语义，因此不能宣称所有工具参数100%正确。",
        "- 政策 Recall@5：需要政策的案例是否检索到预期政策；缺少订单/商品的澄清案例不计入分母。未检索按失败计。当前只有两项有效政策，并先按意图过滤，这不是大型RAG检索能力测试。",
        "- 方案引用正确性：只对实际产生的方案，检查政策ID、版本内容哈希和引用原文是否与检索结果一致；不评价自由语言回答质量。",
        "- 延迟：预热后每案例的真实模型、MCP、审批和执行总耗时，包含等待与数据库开销；本地BGE CPU、经SSH访问服务器。Qwen并发4个案例、vLLM最多2序列，基线/DeepSeek各2；运行有时间重叠，不能当作严格隔离的模型速度榜。",
        "- 费用：Qwen不产生按token API账单，未折算GPU电费。DeepSeek按返回token以输入最高2元/百万、输出最高8元/百万保守计费；未知用量保留预留。不是供应商发票金额或整个账号消费。",
        "",
        "## 完整测试集",
        "",
        "| 配置 | 任务成功 | 关键工具参数 | 政策 Recall@5 | 方案引用 | 平均/P95秒 | API费用上界/元 |",
        "|---|---|---|---|---|---|---|",
    ]
    for repeat in range(1, 4):
        lines.append(
            table_row(f"Qwen 第{repeat}轮", [r for r in qwen if r["repeat"] == repeat])
        )
    lines += [table_row("Qwen 三轮合计", qwen), table_row("固定工作流", fixed), ""]
    success = sum(r["passed"] for r in qwen) / len(qwen)
    lines += [
        f"Qwen任务成功率目标80%：**{'达到' if success >= 0.8 else '未达到'}**（实测{success:.1%}）。三次重复不是450条独立测试样本。固定工作流与Agent使用相同业务工具和政策；基线不读测试标签，且只用于评测。",
        "",
        "## 预先选定的30条分层子集",
        "",
        "每个测试情景族取前两个变体，选择在运行前冻结。下面Qwen仅统计相同30条的三次运行，不能把DeepSeek的30条成绩当成150条完整测试成绩。",
        "",
        "| 配置 | 任务成功 | 关键工具参数 | 政策 Recall@5 | 方案引用 | 平均/P95秒 | API费用上界/元 |",
        "|---|---|---|---|---|---|---|",
    ]
    subset_ids = {r["scenario_id"] for r in deepseek}
    lines += [
        table_row(
            "Qwen 相同子集×3", [r for r in qwen if r["scenario_id"] in subset_ids]
        ),
        table_row("DeepSeek 子集", deepseek),
        "",
        "## 各情景成功数",
        "",
        "| 情景族 | Qwen三轮 | 固定工作流 | DeepSeek子集 |",
        "|---|---|---|---|",
    ]
    for family in sorted({r["family"] for r in qwen}):
        lines.append(
            "| "
            + family
            + " | "
            + " | ".join(
                rate([r["passed"] for r in rows if r["family"] == family])
                for rows in (qwen, fixed, deepseek)
            )
            + " |"
        )
    lines += ["", "## 失败分类与原始证据", ""]
    for name, report in reports.items():
        failures = [r for r in report["results"] if not r["passed"]]
        counts = Counter(
            (
                r["failure"].split(":", 1)[0]
                if r["failure"]
                else f"终态 {r['observed']}，预期 {r['expected']}"
            )
            for r in failures
        )
        lines += [
            f"### {name}",
            "",
            f"失败 {len(failures)}/{len(report['results'])}；分类："
            + "；".join(f"{k} × {v}" for k, v in counts.items()),
            "",
        ]
        seen = set()
        for row in failures:
            if row["family"] in seen:
                continue
            seen.add(row["family"])
            reason = row["failure"] or f"返回{row['observed']}，预期{row['expected']}"
            lines.append(
                f"- `{row['scenario_id']}` / 第{row['repeat']}轮 / `{row['case_id']}`：{reason}"
            )
        actual = sorted({m for r in report["results"] for m in r["actual_models"]})
        lines += [
            "",
                f"原始结果：[JSON]({name}.json)。代码 `{report['git_commit']}`；实际模型：`{', '.join(actual) or '无模型'}`。运行时间：{report['started_at']} 至 {report['finished_at']}。工作区脏标记：{report['working_tree_dirty']}（生成报告及前端类型文件也会触发；运行进程从记录的提交加载调查核心）。",
            "",
        ]
    lines += [
        "## 结论的适用范围",
        "",
        "工程安全约束与模型任务成功是两个指标。模型可能在确定性资格拒绝后反复调用、错误要求补充信息或达到12次调用上限；这些计为失败，即使没有越权执行。模型返回的 no_action 也不等同于已解决用户问题。评测直接运行调查器，抛异常时记录原状态 investigating；产品worker则会持久化 stopped 和原因。",
        "",
        "本项目的主要证据是工具事实约束、审批/确认边界、跨服务幂等和真实进程恢复。不能据此声称小模型全面优于固定流程，也不能把两条政策的召回结果包装成企业知识库能力。多轮澄清、换单授权失效和恢复另见工程测试证据，不由本单轮集推导。",
        "",
    ]
    (REPORTS / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print("Generated", REPORTS / "REPORT.md")


if __name__ == "__main__":
    main()
