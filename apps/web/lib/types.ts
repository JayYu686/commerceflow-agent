export type HealthResponse = {
  service: string;
  status: "ok";
  environment: string;
  timestamp: string;
};

export type CustomerSummary = {
  id: number;
  name: string;
  tier: string;
  risk_flag: boolean;
};

export type ProductSummary = {
  id: number;
  sku: string;
  name: string;
  category: string;
  aftersales_type: string;
};

export type OrderItem = {
  quantity: number;
  unit_price: string;
  line_amount: string;
  product: ProductSummary;
};

export type OrderFacts = {
  order_no: string;
  status: string;
  aftersales_status: string;
  paid_amount: string;
  currency: string;
  paid_at: string;
  delivered_at: string | null;
  customer: CustomerSummary;
  items: OrderItem[];
};

export type ShipmentEvent = {
  sequence: number;
  event_type: string;
  occurred_at: string;
  location: string;
  description: string;
};

export type LogisticsFacts = {
  order_no: string;
  carrier: string;
  tracking_no: string;
  status: string;
  promised_at: string;
  shipped_at: string | null;
  delivered_at: string | null;
  last_event_at: string | null;
  events: ShipmentEvent[];
};

export type FactEvidence = {
  source: string;
  field: string;
  value: string;
};

export type PolicyEvidence = {
  policy_id: string;
  chunk_id: string;
  title: string;
  section: string;
  version: string;
  category: string;
  aftersales_type: string;
  intent: string;
  effective_from: string;
  effective_to: string | null;
  score: number;
  content_excerpt: string;
};

export type PreviewRecommendation = {
  action_type: string;
  action_status: "preview_only";
  summary: string;
  proposed_amount: string | null;
  currency: string | null;
  reasons: string[];
  next_steps: string[];
};

export type RiskAssessment = {
  level: "low" | "medium" | "high" | "critical";
  requires_approval: boolean;
  reasons: string[];
};

export type WorkflowStep = {
  name: string;
  status: string;
  detail: string;
};

export type LLMMetadata = {
  provider: string;
  model: string | null;
  used_for: string[];
  fallback_used: boolean;
  fallback_reason: string | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  estimated_cost: string | null;
  latency_ms: number | null;
};

export type AgentError = {
  code: string;
  message: string;
};

export type AgentPreviewRequest = {
  message: string;
  as_of?: string;
};

export type AgentPreviewResponse = {
  status: string;
  intent: string | null;
  order_no: string | null;
  facts: {
    order: OrderFacts | null;
    logistics: LogisticsFacts | null;
  };
  fact_evidence: FactEvidence[];
  policy_evidence: PolicyEvidence[];
  recommendation: PreviewRecommendation;
  risk: RiskAssessment;
  customer_reply: string;
  llm: LLMMetadata;
  errors: AgentError[];
  steps: WorkflowStep[];
};

export type ExecutionStatus = "not_executed" | "not_applicable" | "executed" | "execution_failed";

export type ActionPlanCreateResponse = {
  action_plan_id: string;
  run_id: string;
  order_no: string | null;
  intent: string;
  planned_tool_name: string | null;
  action_type: string;
  status: string;
  execution_status: ExecutionStatus;
  risk_level: string;
  requires_approval: boolean;
  approval_id: string | null;
  proposed_amount: string | null;
  currency: string | null;
  summary: string;
  created_at: string;
};

export type ApprovalSummary = {
  approval_id: string;
  status: string;
  risk_level: string;
  requested_action_type: string;
  proposed_amount: string | null;
  currency: string | null;
  requested_at: string;
  decided_at: string | null;
};

export type ActionPlanResponse = {
  action_plan_id: string;
  run_id: string;
  request_message: string;
  order_no: string | null;
  intent: string;
  planned_tool_name: string | null;
  action_type: string;
  status: string;
  execution_status: ExecutionStatus;
  risk_level: string;
  requires_approval: boolean;
  proposed_amount: string | null;
  currency: string | null;
  summary: string;
  reasons: string[];
  next_steps: string[];
  fact_evidence: FactEvidence[] | Record<string, unknown>[];
  policy_evidence: PolicyEvidence[] | Record<string, unknown>[];
  llm: Record<string, unknown>;
  approval: ApprovalSummary | null;
  created_at: string;
  updated_at: string;
};

export type ActionPlanListItem = ActionPlanCreateResponse & {
  updated_at: string;
};

export type ActionPlanListResponse = {
  action_plans: ActionPlanListItem[];
};

export type ApprovalRequestResponse = {
  approval_id: string;
  action_plan_id: string;
  status: string;
  risk_level: string;
  requested_action_type: string;
  proposed_amount: string | null;
  currency: string | null;
  policy_ids: string[];
  requester: string;
  reviewer: string | null;
  decision_comment: string | null;
  requested_at: string;
  decided_at: string | null;
  updated_at: string;
  action_plan: ActionPlanCreateResponse;
};

export type ApprovalRequestListResponse = {
  approvals: ApprovalRequestResponse[];
};

export type ApprovalDecisionRequest = {
  decision: "approve" | "reject";
  reviewer: string;
  comment?: string | null;
};

export type ToolExecutionResponse = {
  tool_name: "refund_apply" | "coupon_issue" | "ticket_create";
  status: string;
  record_id: string;
  action_plan_id: string;
  order_no: string;
  execution_status: "executed";
  idempotent_replay: boolean;
  created_at: string;
};

export type RefundApplyRequest = {
  action_plan_id: string;
  approval_id: string;
  order_no: string;
  amount: string;
  currency: string;
  reason: string;
};

export type CouponIssueRequest = {
  action_plan_id: string;
  approval_id: string | null;
  order_no: string;
  amount: string;
  currency: string;
  reason: string;
};

export type TicketCreateRequest = {
  action_plan_id: string;
  order_no: string;
  category: string;
  summary: string;
};

export type RefundRecordResponse = {
  refund_id: string;
  action_plan_id: string;
  approval_id: string;
  order_no: string;
  amount: string;
  currency: string;
  reason: string;
  status: "succeeded";
  tool_name: "refund_apply";
  created_at: string;
};

export type CouponRecordResponse = {
  coupon_id: string;
  action_plan_id: string;
  approval_id: string | null;
  order_no: string;
  amount: string;
  currency: string;
  reason: string;
  status: "issued";
  tool_name: "coupon_issue";
  created_at: string;
};

export type TicketRecordResponse = {
  ticket_id: string;
  action_plan_id: string;
  order_no: string;
  category: string;
  summary: string;
  status: "created";
  tool_name: "ticket_create";
  created_at: string;
};

export type ActionPlanResultResponse = {
  action_plan_id: string;
  result_type: "refund" | "coupon" | "ticket" | null;
  result: RefundRecordResponse | CouponRecordResponse | TicketRecordResponse | null;
};

export type AuditLogEvent = {
  event_id: string;
  event_type: string;
  actor_type: string;
  actor_id: string | null;
  action_plan_id: string | null;
  approval_id: string | null;
  order_no: string | null;
  idempotency_key: string | null;
  payload: Record<string, unknown>;
  created_at: string;
};

export type AuditLogListResponse = {
  events: AuditLogEvent[];
};

export type ApiError = {
  status: number;
  code: string;
  message: string;
  existing_identifier?: string | null;
  details?: unknown;
};

export type DemoScenario = {
  id:
    | "quality_refund"
    | "logistics_delay"
    | "bypass_attack"
    | "logistics_delay_short"
    | "missing_order_no_quality";
  title: string;
  message: string;
  expected: string[];
  expectedPreview: {
    status?: string;
    intent?: string;
    recommendation?: string;
    risk?: string;
    requiresApproval?: boolean;
    actionPlanStatus?: string;
    policyId?: string;
  };
};
