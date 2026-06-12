type Tone = "neutral" | "success" | "warning" | "danger" | "critical" | "info";

const labels: Record<string, string> = {
  action_plan_created: "动作计划已创建",
  action_plan_not_found: "动作计划不存在",
  action_plan_not_planned: "动作计划状态不允许执行",
  action_plan_not_executable: "动作计划不可执行",
  action_plan_already_executed: "动作计划已执行",
  apparel: "服饰",
  appliance: "家电",
  approval_requested: "已发起审批",
  approval_approved: "审批已批准",
  approval_rejected: "审批已拒绝",
  approval_already_decided: "审批已完成",
  approval_mismatch: "审批记录不匹配",
  approval_not_approved: "审批尚未批准",
  approval_required: "需要先审批",
  approved: "已批准",
  amount_mismatch: "金额不匹配",
  blocked: "已拦截",
  completed: "已完成",
  coupon: "优惠券补偿",
  coupon_issue: "发放本地模拟优惠券",
  created: "已创建",
  critical: "严重",
  delayed: "已延迟",
  delay_compensation_review: "延误补偿审核预览",
  delivered: "已签收",
  disabled: "已禁用",
  duplicate_action_plan: "重复动作计划",
  duplicate_execution: "重复工具执行",
  customer_reply: "面向用户回复",
  customer_reply_failed: "用户回复生成失败",
  currency_mismatch: "币种不匹配",
  electronics: "电子产品",
  escalate_to_human: "转人工处理",
  executed: "已执行",
  execution_failed: "执行失败",
  fallback: "已回退",
  fake: "本地假模型",
  final_sale: "最终销售",
  fresh: "生鲜",
  generate_customer_reply: "生成面向用户回复",
  high: "高",
  home: "家居",
  in_transit: "运输中",
  issued: "已发放",
  idempotency_key_reused: "幂等键被不同请求复用",
  intent_extraction: "意图抽取",
  intent_extraction_failed: "意图抽取失败",
  intent_extraction_unverified_order_number: "模型返回了未验证订单号",
  logistics_delay_compensation: "物流延迟补偿",
  low: "低",
  manual_review: "人工审核",
  medium: "中",
  missing_policy_evidence: "缺少政策依据",
  needs_more_info: "需要补充信息",
  no_policy_evidence: "缺少政策依据",
  none: "无",
  not_applicable: "不适用",
  not_executable: "不可执行",
  not_executed: "未执行",
  not_found: "未找到",
  not_required: "无需审批",
  not_used: "未启用",
  order_mismatch: "订单号不匹配",
  openai_compatible: "OpenAI 兼容模型",
  pending: "待审批",
  pending_approval: "待审批",
  perishable: "易腐商品",
  picked_up: "已揽收",
  planned: "已计划",
  preview_only: "仅预览，不执行",
  provider_disabled: "模型未启用",
  quality_issue_refund: "质量问题退款",
  rejected: "已拒绝",
  departed: "已离开发件分拣中心",
  refund: "退款",
  refund_apply: "申请本地模拟退款",
  refund_review: "退款审核预览",
  request_more_info: "请求补充信息",
  required: "需要审批",
  reviewer: "审批人",
  running: "运行中",
  shipped: "已发货",
  special: "特殊售后",
  standard: "标准售后",
  succeeded: "已成功",
  ticket: "工单",
  ticket_create: "创建本地模拟工单",
  tool_action_mismatch: "工具动作不匹配",
  tool_execution_blocked: "工具执行已拦截",
  tool_execution_failed: "工具执行失败",
  tool_execution_idempotent_replay: "工具幂等重放",
  tool_execution_succeeded: "工具执行成功",
  unknown: "未识别",
  used: "已启用",
  verify_order: "核验订单",

  parse_request: "解析用户请求",
  llm_understand_request: "受控 LLM 辅助理解",
  validate_context: "校验上下文",
  query_order_facts: "查询订单事实",
  query_logistics_facts: "查询物流事实",
  retrieve_policy: "检索政策依据",
  recommend_action: "生成处理建议",
  classify_risk: "风险分级",
  build_response: "构建预览响应",

  system: "系统",
  user: "用户",
  agent_preview: "Agent 预览流程",
  approval_reviewer: "审批人",
  tool_service: "工具执行服务",
};

const evaluationLabels: Record<string, string> = {
  action_proposal_accuracy: "动作建议准确率",
  approval_enforcement_rate: "审批执行约束率",
  citation_grounded_rate: "引用依据覆盖率",
  duplicate_refund_execution_blocked: "重复退款执行拦截",
  high_coupon_without_approval_blocked: "高额优惠券无审批拦截",
  human_escalation_accuracy: "人工升级判断准确率",
  idempotency_protection_rate: "幂等保护率",
  intent_accuracy: "意图识别准确率",
  logistics_delay: "物流延迟补偿",
  missing_or_ambiguous_context: "缺少或含混上下文",
  missing_order_no: "缺少订单号",
  order_no_accuracy: "订单号识别准确率",
  order_not_found: "订单不存在",
  order_status_unchanged: "目标订单售后状态未变化",
  policy_recall_at_k: "政策召回率",
  protected_tables_unchanged: "受保护业务表未变化",
  quality_refund: "质量问题退款",
  rejected_refund_blocked: "已拒绝审批拦截退款",
  risk_classification_accuracy: "风险分级准确率",
  status_accuracy: "状态准确率",
  task_success_rate: "任务成功率",
  tool_argument_accuracy: "工具参数准确率",
  tool_safety: "工具执行安全",
  trace_completeness: "审计轨迹完整率",
  unsafe_action_block_rate: "越权动作拦截率",
  unsafe_instruction: "越权指令拦截",
};

const fieldLabels: Record<string, string> = {
  action_plan_id: "动作计划 ID",
  actor_id: "操作者 ID",
  actor_type: "操作者类型",
  aftersales_status: "售后状态",
  aftersales_type: "售后类型",
  amount: "金额",
  approval_id: "审批 ID",
  category: "品类",
  chunk_id: "政策片段 ID",
  created_at: "创建时间",
  currency: "币种",
  decision_comment: "审批意见",
  decided_at: "决策时间",
  delivered_at: "签收时间",
  event_id: "事件 ID",
  event_type: "事件类型",
  execution_status: "执行状态",
  fact_evidence: "事实依据",
  idempotency_key: "幂等键",
  intent: "意图",
  last_event_at: "最后物流事件时间",
  order_no: "订单号",
  paid_amount: "支付金额",
  planned_tool_name: "计划工具",
  policy_evidence: "政策依据",
  policy_id: "政策 ID",
  proposed_amount: "建议金额",
  reason: "原因",
  request_hash: "请求哈希",
  requested_action_type: "请求动作",
  requested_at: "发起时间",
  requires_approval: "需要审批",
  result_status: "结果状态",
  risk_level: "风险等级",
  run_id: "运行 ID",
  section: "政策章节",
  status: "状态",
  summary: "摘要",
  tool_name: "工具名称",
  tracking_no: "运单号",
  updated_at: "更新时间",
  value: "值",
};

const sourceLabels: Record<string, string> = {
  logistics: "物流事实",
  order: "订单事实",
  product: "商品事实",
};

const policyTitles: Record<string, string> = {
  "Apparel Size Exchange Policy": "服饰尺码换货政策",
  "Appliance Warranty Service Policy": "家电保修服务政策",
  "Deprecated Electronics Quality Refund Policy": "已废弃的电子产品质量退款政策",
  "Electronics Quality Issue Refund Policy": "电子产品质量问题退款政策",
  "Expired Logistics Delay Compensation Policy": "已过期的物流延迟补偿政策",
  "Final Sale Exclusion Policy": "最终销售商品售后限制政策",
  "Fresh Perishable After-sales Policy": "生鲜易腐商品售后政策",
  "Home Goods Damaged Item Policy": "家居商品损坏售后政策",
  "Logistics Delay Compensation Policy": "物流延迟补偿政策",
};

const policyIdTitles: Record<string, string> = {
  "POL-QUALITY-ELECTRONICS-V2": "电子产品质量问题退款政策",
  "POL-LOGISTICS-DELAY-V1": "物流延迟补偿政策",
  "POL-FRESH-PERISHABLE-V1": "生鲜易腐商品售后政策",
  "POL-FINAL-SALE-V1": "最终销售商品售后限制政策",
};

const policySections: Record<string, string> = {
  "Approval Rule": "审批规则",
  "Carrier Damage": "运输损坏",
  "Condition Requirement": "商品状态要求",
  "Damage Evidence": "损坏证据",
  "Delay Definition": "延迟定义",
  "Disclosure": "信息披露",
  "Eligible Orders": "适用订单",
  "Eligibility": "适用条件",
  "Evidence": "证据要求",
  "Exclusions": "不适用情形",
  "Expired Amount": "已过期金额规则",
  "Expired Delay Rule": "已过期延迟规则",
  "Historical Context": "历史上下文",
  "High Value Compensation": "高额补偿",
  "Manual Approval": "人工审批",
  "Manual Review": "人工复核",
  "No Evidence": "缺少证据",
  "No Return": "不可退货",
  "Old Eligibility": "旧版适用条件",
  "Old Evidence": "旧版证据要求",
  "Proof": "证明材料",
  "Refund Boundary": "退款边界",
  "Refund Escalation": "退款升级处理",
  "Refund Limit": "退款金额限制",
  "Reporting Window": "反馈时限",
  "Replacement Review": "换货审核",
  "Resolution Options": "处理选项",
  "Shipping": "运费规则",
  "Small Compensation": "小额补偿",
  "Storage Exclusion": "储存不当排除",
  "Warranty Scope": "保修范围",
};

const textMap: Record<string, string> = {
  "Action plan created for after-sales preview.": "已基于售后预览创建动作计划。",
  "Active policy evidence found: POL-QUALITY-ELECTRONICS-V2.": "已命中有效政策依据：电子产品质量问题退款政策。",
  "Active policy evidence found: POL-LOGISTICS-DELAY-V1.": "已命中有效政策依据：物流延迟补偿政策。",
  "Agent preview generated action plan.": "Agent 预览已生成动作计划。",
  "Ask a human reviewer to inspect the logistics timeline.": "请人工复核物流时间线。",
  "Ask a human reviewer to inspect the order and logistics records.": "请人工复核订单和物流记录。",
  "Ask the user for a single order number.": "请用户补充一个明确的订单号。",
  "Ask the user to confirm the order number.": "请用户核对订单号。",
  "Ask the user which order should be reviewed.": "请用户确认需要审核哪一个订单。",
  "Ask the user to describe the issue type.": "请用户说明是商品质量问题还是物流延迟问题。",
  "A preview must be grounded on one order snapshot.": "一次预览必须基于一个明确的订单快照。",
  "Collect defect evidence from the customer.": "请向用户收集故障证据，例如照片、视频或清晰的问题描述。",
  "Confirm carrier delay details.": "请确认承运商物流延迟细节。",
  "Context is sufficient.": "上下文信息已满足继续处理条件。",
  "Customer reply generated from validated evidence context.": "已基于校验后的事实和政策依据生成用户回复。",
  "Delay compensation requires logistics delay evidence.": "延误补偿必须有物流延迟事实依据。",
  "Generated delay compensation preview.": "已生成延误补偿审核预览。",
  "Generated deterministic customer reply.": "已生成确定性用户回复。",
  "Generated refund review preview.": "已生成退款审核预览。",
  "Intent requires clarification.": "需要进一步明确售后意图。",
  "Keep this as preview until Phase 4 controlled tools exist.": "在受控工具执行前，该建议仅作为预览保留。",
  "LLM candidate included an order number not extracted deterministically.": "LLM 返回了未被确定性解析器识别的订单号，已拒绝该候选结果。",
  "LLM customer reply rejected; deterministic reply used.": "LLM 回复未通过校验，已改用确定性回复。",
  "LLM intent candidate rejected; deterministic parser remains authoritative.": "LLM 意图候选未通过校验，继续以确定性解析为准。",
  "LLM intent candidate validated as auxiliary signal.": "LLM 意图候选已通过校验，仅作为辅助信号使用。",
  "LLM provider disabled; deterministic parser remains authoritative.": "LLM 未启用，当前以确定性解析为准。",
  "Logistics facts do not show a delayed shipment. Escalate for manual review.": "物流事实未显示延迟，建议转人工复核。",
  "Logistics service returned not found.": "未查询到物流记录。",
  "Logistics facts loaded.": "物流事实已加载。",
  "Logistics status does not show delay evidence.": "物流状态未显示延迟依据。",
  "Missing order number.": "缺少订单号。",
  "Missing required facts or policy evidence requires manual review.": "缺少必要事实或政策依据，需要人工复核。",
  "Multiple order numbers found.": "请求中包含多个订单号。",
  "Multiple order numbers were found.": "请求中识别到多个订单号。",
  "Multiple order numbers were provided.": "用户提供了多个订单号，需要先明确处理哪一个订单。",
  "No active applicable policy evidence was found.": "未找到当前有效且适用的政策依据。",
  "No business execution is proposed.": "当前未提出任何业务执行动作。",
  "No executable action is proposed.": "当前未提出可执行动作。",
  "No execution proposed.": "当前没有提出执行动作。",
  "No logistics evidence is available for a logistics compensation request.": "物流补偿请求缺少必要物流事实依据。",
  "No order number was found.": "未识别到订单号。",
  "No order number was provided.": "用户未提供订单号。",
  "No movement update for more than 72 hours.": "超过 72 小时没有物流轨迹更新。",
  "Order was not found in commerce facts.": "订单事实库中未找到该订单。",
  "Order facts loaded.": "订单事实已加载。",
  "Order facts must come from the commerce service.": "订单事实必须来自受控的订单查询服务。",
  "Order service returned not found.": "订单服务返回未找到。",
  "Parsed message deterministically.": "已使用确定性规则解析用户消息。",
  "Please clarify whether this is a quality issue refund or logistics delay request.": "请明确这是商品质量问题退款，还是物流延迟补偿。",
  "Please provide one order number per preview request.": "每次预览请求请只提供一个订单号。",
  "Please provide the order number before after-sales review can continue.": "请先提供订单号，系统才能继续售后审核预览。",
  "Policy evidence loaded.": "政策依据已加载。",
  "Policy retrieval returned empty hits.": "政策检索没有命中有效结果。",
  "Preview blocked because the request attempts to bypass approval or execution rules.": "请求试图绕过审批或执行规则，预览已被拦截。",
  "Preview only: logistics delay compensation review may be prepared.": "仅预览：可以准备物流延迟补偿审核。",
  "Preview only: quality issue refund review may be prepared after evidence review.": "仅预览：完成证据审核后，可以准备质量问题退款审核。",
  "Preview response built.": "预览响应已构建完成。",
  "Prompt instructions cannot override safety rules.": "用户提示不能覆盖系统安全规则。",
  "Refund actions require human approval.": "退款动作必须经过人工审批。",
  "Refund execution is high risk and requires human approval.": "退款执行属于高风险动作，必须人工审批。",
  "Required facts are missing. Escalate for manual review.": "缺少必要事实，建议转人工复核。",
  "Required facts were missing.": "缺少必要事实。",
  "Request attempts to bypass approval or directly execute a business action.": "请求试图绕过审批或直接执行业务动作。",
  "Request attempts to bypass controlled execution.": "请求试图绕过受控执行流程。",
  "Request is blocked by safety rules.": "请求已被安全规则拦截。",
  "Risk classified deterministically.": "已使用确定性规则完成风险分级。",
  "Send the proposed refund for human approval before any execution.": "执行前必须先将拟退款动作提交人工审批。",
  "Small compensation preview is medium risk and does not execute a coupon.": "小额补偿预览为中风险，当前不会直接发放优惠券。",
  "Submit a normal after-sales request without bypass instructions.": "请提交不包含绕过审批或直接执行要求的正常售后诉求。",
  "The after-sales intent is unclear.": "售后意图尚不明确。",
  "The deterministic classifier could not identify a supported intent.": "确定性分类器未识别到支持的售后意图。",
  "The order number was not found. Verify the order number before continuing.": "未查询到该订单，请先核对订单号。",
  "The preview amount is within the CNY 10 small-compensation threshold.": "预览金额在 CNY 10 小额补偿阈值内。",
  "The preview did not reach an executable recommendation.": "当前预览未形成可执行建议。",
  "Tool facts override user claims.": "工具查询到的事实优先于用户描述。",
  "Unsupported action without policy evidence is not allowed.": "没有政策依据时，不允许生成受支持的执行建议。",
  "Unsafe request blocked.": "不安全请求已被拦截。",
  "Have a human reviewer inspect the request and policy gap.": "请人工复核该请求与政策缺口。",
  "Supported after-sales intent was not found.": "未识别到当前系统支持的售后意图。",
  "Review the request manually.": "请人工复核该请求。",
  "Shipment record created.": "已创建物流记录。",
  "Package picked up by carrier.": "承运商已揽收包裹。",
  "Package departed origin sort center.": "包裹已离开发件地分拣中心。",
  "Shanghai Fulfillment Center": "上海履约中心",
  "Shanghai Sort Center": "上海分拣中心",
  "Regional Transit Hub": "区域转运中心",
};

const policyTextMap: Record<string, string> = {
  "A shipment is considered delayed when there is no carrier movement update for more than 72 hours or delivery exceeds the promised time.":
    "当承运商超过 72 小时没有物流轨迹更新，或送达时间超过承诺时效时，可判定为物流延迟。",
  "Any refund action is high risk and must wait for human approval before execution, even when the quality issue is policy eligible.":
    "任何退款动作都属于高风险操作，即使质量问题符合政策，也必须等待人工审批后才能执行。",
  "Compensation above CNY 10 is high risk and must require human approval before any coupon can be issued.":
    "超过 CNY 10 的补偿属于高风险，发放任何优惠券前必须经过人工审批。",
  "Customers should provide photos, video, or a clear description showing the defect, such as a headphone speaker with no sound or intermittent audio.":
    "用户应提供照片、视频或清晰的问题描述，用于证明故障，例如耳机无声或声音断续。",
  "Delay compensation may apply to paid orders that are not cancelled and have a valid tracking number with carrier events.":
    "物流延迟补偿适用于已支付、未取消，且具备有效运单号和承运商轨迹事件的订单。",
  "For standard electronics, quality defects reported within 7 days after delivery may qualify for return and refund after evidence review.":
    "标准电子产品在签收后 7 天内反馈质量缺陷，经证据审核后可进入退货退款审核。",
  "If logistics events are missing or inconsistent, the case should be escalated instead of fabricating delay evidence.":
    "如果物流事件缺失或不一致，应转人工处理，不能编造延迟依据。",
  "The refundable amount must not exceed the paid order amount for the affected item, excluding unrelated shipping or coupon adjustments.":
    "可退金额不得超过受影响商品的实付金额，不包含无关运费或优惠调整。",
  "A small coupon may be proposed for eligible logistics delay cases when the amount is within the configured automatic compensation limit.":
    "符合条件的物流延迟场景，在金额不超过配置的小额补偿阈值时，可提出小额优惠券补偿建议。",
};

export function displayLabel(value: string | null | undefined, fallback = "未提供"): string {
  if (!value) {
    return fallback;
  }
  return labels[value] ?? evaluationLabels[value] ?? value;
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

export function fieldLabel(value: string | null | undefined): string {
  if (!value) {
    return "字段";
  }
  return fieldLabels[value] ?? value;
}

export function sourceLabel(value: string | null | undefined): string {
  if (!value) {
    return "来源";
  }
  return sourceLabels[value] ?? displayLabel(value);
}

export function policyTitle(value: string | null | undefined): string {
  if (!value) {
    return "未命名政策";
  }
  return policyTitles[value] ?? value;
}

export function policyIdTitle(value: string | null | undefined): string {
  if (!value) {
    return "未知政策";
  }
  return policyIdTitles[value] ? `${policyIdTitles[value]}（${value}）` : value;
}

export function policySection(value: string | null | undefined): string {
  if (!value) {
    return "未命名章节";
  }
  return policySections[value] ?? value;
}

export function policyExcerpt(value: string | null | undefined): string {
  if (!value) {
    return "无政策摘要。";
  }
  return policyTextMap[value] ?? localizeText(value);
}

export function localizeText(value: string | null | undefined): string {
  if (!value) {
    return "无";
  }
  if (textMap[value]) {
    return textMap[value];
  }
  if (policyTextMap[value]) {
    return policyTextMap[value];
  }

  let match = value.match(/^Order (.+) was found with status (.+)\.$/);
  if (match) {
    return `订单 ${match[1]} 已查到，订单状态为“${displayLabel(match[2])}”。`;
  }

  match = value.match(/^Active policy evidence found: (.+)\.$/);
  if (match) {
    const policyLabels = match[1]
      .split(",")
      .map((item) => policyIdTitle(item.trim()))
      .join("、");
    return `已命中有效政策依据：${policyLabels}。`;
  }

  match = value.match(/^Shipment (.+) has status (.+)\.$/);
  if (match) {
    return `运单 ${match[1]} 当前物流状态为“${displayLabel(match[2])}”。`;
  }

  match = value.match(/^Order (.+) was not found\.$/);
  if (match) {
    return `未查询到订单 ${match[1]}。`;
  }

  match = value.match(/^Logistics for (.+) was not found\.$/);
  if (match) {
    return `未查询到订单 ${match[1]} 的物流记录。`;
  }

  return value;
}

export function localizeTextList(values: string[]): string[] {
  return values.map((value) => localizeText(value));
}

export function payloadKeyLabel(key: string): string {
  return fieldLabel(key);
}

export function payloadValueLabel(key: string, value: unknown): string {
  if (value === null || value === undefined) {
    return "无";
  }
  if (typeof value === "boolean") {
    return yesNo(value);
  }
  if (typeof value === "string") {
    if (
      key.endsWith("status") ||
      key === "tool_name" ||
      key === "event_type" ||
      key === "actor_type" ||
      key === "intent" ||
      key === "risk_level" ||
      key === "requested_action_type"
    ) {
      return displayLabel(value);
    }
    return localizeText(value);
  }
  if (typeof value === "number") {
    return String(value);
  }
  return JSON.stringify(value);
}

export function actorLabel(actorType: string, actorId?: string | null): string {
  const actor = displayLabel(actorType);
  return actorId ? `${actor} / ${displayLabel(actorId)}` : actor;
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
