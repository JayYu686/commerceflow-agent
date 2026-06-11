type Tone = "neutral" | "success" | "warning" | "danger" | "critical" | "info";

const labels: Record<string, string> = {
  completed: "已完成",
  blocked: "已拦截",
  needs_more_info: "需要补充信息",
  not_found: "未找到",
  no_policy_evidence: "缺少政策依据",
  quality_issue_refund: "质量问题退款",
  logistics_delay_compensation: "物流延迟补偿",
  unknown: "未识别",
  refund_review: "退款审核预览",
  delay_compensation_review: "延误补偿审核预览",
  escalate_to_human: "转人工处理",
  request_more_info: "请求补充信息",
  blocked_action: "已拦截动作",
  preview_only: "仅预览",
  pending_approval: "待审批",
  approved: "已批准",
  rejected: "已拒绝",
  planned: "已计划",
  not_executed: "未执行",
  not_applicable: "不适用",
  not_executable: "不可执行",
  executed: "已执行",
  execution_failed: "执行失败",
  high: "高",
  medium: "中",
  low: "低",
  critical: "严重",
  standard: "标准售后",
  special: "特殊售后",
  perishable: "易腐商品",
  final_sale: "最终销售",
  electronics: "电子产品",
  fresh: "生鲜",
  home: "家居",
  apparel: "服饰",
  appliance: "家电",
  delivered: "已签收",
  delayed: "已延迟",
  in_transit: "运输中",
  none: "无",
  required: "需要审批",
  not_required: "无需审批",
  used: "已启用",
  not_used: "未启用",
  disabled: "已禁用",
  fallback: "已回退",
  parse_request: "解析请求",
  llm_understand_request: "受控 LLM 理解",
  validate_context: "校验上下文",
  query_order_facts: "查询订单事实",
  query_logistics_facts: "查询物流事实",
  retrieve_policy: "检索政策依据",
  recommend_action: "生成处理建议",
  classify_risk: "风险分级",
  generate_customer_reply: "生成面向用户回复",
  build_response: "构建预览响应",
};

export function displayLabel(value: string | null | undefined, fallback = "未提供"): string {
  if (!value) {
    return fallback;
  }
  return labels[value] ?? value;
}

export function displayWithRaw(value: string | null | undefined, fallback = "未提供"): {
  label: string;
  raw: string | null;
} {
  if (!value) {
    return { label: fallback, raw: null };
  }
  return { label: displayLabel(value, fallback), raw: value };
}

export function yesNo(value: boolean | null | undefined): string {
  if (value === undefined || value === null) {
    return "未知";
  }
  return value ? "是" : "否";
}

export function toneForRiskValue(risk?: string | null): Tone {
  if (risk === "critical") {
    return "critical";
  }
  if (risk === "high") {
    return "danger";
  }
  if (risk === "medium") {
    return "warning";
  }
  if (risk === "low") {
    return "success";
  }
  return "neutral";
}

export function toneForStatusValue(status?: string | null): Tone {
  if (status === "completed" || status === "planned" || status === "approved" || status === "executed") {
    return "success";
  }
  if (status === "pending_approval" || status === "preview_only" || status === "not_executed") {
    return "warning";
  }
  if (status === "blocked" || status === "critical" || status === "not_executable") {
    return "critical";
  }
  if (status === "not_found" || status === "no_policy_evidence" || status === "execution_failed") {
    return "danger";
  }
  return "neutral";
}
