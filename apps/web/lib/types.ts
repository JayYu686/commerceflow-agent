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

export type ActionPlanCreateResponse = {
  action_plan_id: string;
  run_id: string;
  order_no: string | null;
  intent: string;
  planned_tool_name: string | null;
  action_type: string;
  status: string;
  execution_status: "not_executed" | "not_applicable" | "executed" | "execution_failed";
  risk_level: string;
  requires_approval: boolean;
  approval_id: string | null;
  proposed_amount: string | null;
  currency: string | null;
  summary: string;
  created_at: string;
};

export type ApiError = {
  status: number;
  code: string;
  message: string;
  existing_identifier?: string | null;
  details?: unknown;
};

export type DemoScenario = {
  id: "quality_refund" | "logistics_delay" | "bypass_attack";
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
  };
};
