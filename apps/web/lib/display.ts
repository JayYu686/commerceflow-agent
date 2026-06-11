type Tone = "neutral" | "success" | "warning" | "danger" | "critical" | "info";

const labels: Record<string, string> = {
  action_plan_created: "动作计划已创建",
  action_plan_not_executable: "动作计划不可执行",
  apparel: "服饰",
  appliance: "家电",
  approval_requested: "已发起审批",
  approval_approved: "审批已批准",
  approval_rejected: "审批已拒绝",
  approved: "已批准",
  blocked: "已拦截",
  completed: "已完成",
  coupon: "优惠券",
  coupon_issue: "发放优惠券",
  created: "已创建",
  critical: "严重",
  delayed: "已延迟",
  delay_compensation_review: "延误补偿审核预览",
  delivered: "已签收",
  disabled: "已禁用",
  electronics: "电子产品",
  escalate_to_human: "转人工处理",
  executed: "已执行",
  execution_failed: "执行失败",
  fallback: "已回退",
  final_sale: "最终销售",
  fresh: "生鲜",
  generate_customer_reply: "生成面向用户回复",
  high: "高",
  home: "家居",
  in_transit: "运输中",
  issued: "已发放",
  logistics_delay_compensation: "物流延迟补偿",
  low: "低",
  manual_review: "人工审核",
  medium: "中",
  needs_more_info: "需要补充信息",
  no_policy_evidence: "缺少政策依据",
  none: "无",
  not_applicable: "不适用",
  not_executable: "不可执行",
  not_executed: "未执行",
  not_found: "未找到",
  not_required: "无需审批",
  not_used: "未启用",
  pending: "待审批",
  pending_approval: "待审批",
  perishable: "易腐商品",
  planned: "已计划",
  preview_only: "仅预览",
  quality_issue_refund: "质量问题退款",
  rejected: "已拒绝",
  refund: "退款",
  refund_apply: "申请退款",
  refund_review: "退款审核预览",
  request_more_info: "请求补充信息",
  required: "需要审批",
  shipped: "已发货",
  special: "特殊售后",
  standard: "标准售后",
  succeeded: "已成功",
  ticket: "工单",
  ticket_create: "创建工单",
  tool_execution_blocked: "工具执行已拦截",
  tool_execution_idempotent_replay: "工具幂等重放",
  tool_execution_succeeded: "工具执行成功",
  unknown: "未识别",
  used: "已启用",
  verify_order: "核验订单",

  parse_request: "解析请求",
  llm_understand_request: "受控 LLM 理解",
  validate_context: "校验上下文",
  query_order_facts: "查询订单事实",
  query_logistics_facts: "查询物流事实",
  retrieve_policy: "检索政策依据",
  recommend_action: "生成处理建议",
  classify_risk: "风险分级",
  build_response: "构建预览响应",
};

export function displayLabel(value: string | null | undefined, fallback = "未提供"): string {
  if (!value) {
    return fallback;
  }
  return labels[value] ?? value;
}

export function displayWithRaw(
  value: string | null | undefined,
  fallback = "未提供",
): {
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

export function money(amount: string | null | undefined, currency: string | null | undefined): string {
  if (!amount) {
    return "无";
  }
  return `${currency ?? ""} ${amount}`.trim();
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "无";
  }
  return value.replace("T", " ").replace("Z", " UTC");
}

export function recordIdLabel(resultType: string | null | undefined): string {
  if (resultType === "refund") {
    return "退款记录 ID";
  }
  if (resultType === "coupon") {
    return "优惠券记录 ID";
  }
  if (resultType === "ticket") {
    return "工单记录 ID";
  }
  return "记录 ID";
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
  if (
    status === "completed" ||
    status === "planned" ||
    status === "approved" ||
    status === "executed" ||
    status === "succeeded" ||
    status === "issued" ||
    status === "created" ||
    status === "tool_execution_succeeded"
  ) {
    return "success";
  }
  if (
    status === "pending" ||
    status === "pending_approval" ||
    status === "preview_only" ||
    status === "not_executed" ||
    status === "tool_execution_idempotent_replay"
  ) {
    return "warning";
  }
  if (
    status === "blocked" ||
    status === "critical" ||
    status === "not_executable" ||
    status === "tool_execution_blocked"
  ) {
    return "critical";
  }
  if (status === "not_found" || status === "no_policy_evidence" || status === "execution_failed") {
    return "danger";
  }
  return "neutral";
}
