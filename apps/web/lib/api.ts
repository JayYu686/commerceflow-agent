import type {
  ActionPlanCreateResponse,
  ActionPlanListResponse,
  ActionPlanResponse,
  ActionPlanResultResponse,
  AgentPreviewRequest,
  AgentPreviewResponse,
  ApiError,
  ApprovalDecisionRequest,
  ApprovalRequestListResponse,
  ApprovalRequestResponse,
  AuditLogListResponse,
  CouponIssueRequest,
  HealthResponse,
  RefundApplyRequest,
  TicketCreateRequest,
  ToolExecutionResponse,
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type ActionPlanFilters = {
  status?: string;
  execution_status?: string;
  order_no?: string;
  limit?: number;
};

export async function getHealth(): Promise<HealthResponse> {
  return apiRequest<HealthResponse>("/health");
}

export async function runPreview(
  request: AgentPreviewRequest,
): Promise<AgentPreviewResponse> {
  return apiRequest<AgentPreviewResponse>("/api/agent/after-sales/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export async function createActionPlan(
  request: AgentPreviewRequest,
  idempotencyKey: string,
) : Promise<ActionPlanCreateResponse> {
  return apiRequest<ActionPlanCreateResponse>("/api/agent/after-sales/action-plans", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey,
    },
    body: JSON.stringify(request),
  });
}

export async function listActionPlans(
  filters: ActionPlanFilters = {},
): Promise<ActionPlanListResponse> {
  return apiRequest<ActionPlanListResponse>(`/api/action-plans${queryString(filters)}`);
}

export async function getActionPlan(actionPlanId: string): Promise<ActionPlanResponse> {
  return apiRequest<ActionPlanResponse>(`/api/action-plans/${encodeURIComponent(actionPlanId)}`);
}

export async function getActionPlanAuditLogs(
  actionPlanId: string,
): Promise<AuditLogListResponse> {
  return apiRequest<AuditLogListResponse>(
    `/api/action-plans/${encodeURIComponent(actionPlanId)}/audit-logs`,
  );
}

export async function getActionPlanResult(
  actionPlanId: string,
): Promise<ActionPlanResultResponse> {
  return apiRequest<ActionPlanResultResponse>(
    `/api/action-plans/${encodeURIComponent(actionPlanId)}/result`,
  );
}

export async function listApprovals(
  status: "pending" | "approved" | "rejected",
  limit = 50,
): Promise<ApprovalRequestListResponse> {
  return apiRequest<ApprovalRequestListResponse>(
    `/api/approvals${queryString({ status, limit })}`,
  );
}

export async function getApproval(approvalId: string): Promise<ApprovalRequestResponse> {
  return apiRequest<ApprovalRequestResponse>(`/api/approvals/${encodeURIComponent(approvalId)}`);
}

export async function decideApproval(
  approvalId: string,
  request: ApprovalDecisionRequest,
  idempotencyKey: string,
): Promise<ApprovalRequestResponse> {
  return apiRequest<ApprovalRequestResponse>(
    `/api/approvals/${encodeURIComponent(approvalId)}/decision`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify(request),
    },
  );
}

export async function executeRefundApply(
  request: RefundApplyRequest,
  idempotencyKey: string,
): Promise<ToolExecutionResponse> {
  return executeTool("/api/tools/refund-apply", request, idempotencyKey);
}

export async function executeCouponIssue(
  request: CouponIssueRequest,
  idempotencyKey: string,
): Promise<ToolExecutionResponse> {
  return executeTool("/api/tools/coupon-issue", request, idempotencyKey);
}

export async function executeTicketCreate(
  request: TicketCreateRequest,
  idempotencyKey: string,
): Promise<ToolExecutionResponse> {
  return executeTool("/api/tools/ticket-create", request, idempotencyKey);
}

async function executeTool<TRequest>(
  path: string,
  request: TRequest,
  idempotencyKey: string,
): Promise<ToolExecutionResponse> {
  return apiRequest<ToolExecutionResponse>(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey,
    },
    body: JSON.stringify(request),
  });
}

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    throw await normalizeApiError(response);
  }

  return (await response.json()) as T;
}

async function normalizeApiError(response: Response): Promise<ApiError> {
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  const detail = isRecord(payload) ? payload.detail : null;
  if (Array.isArray(detail)) {
    return {
      status: response.status,
      code: "validation_error",
      message: detail.map((item) => validationMessage(item)).join("; "),
      details: detail,
    };
  }

  if (isRecord(detail)) {
    return {
      status: response.status,
      code: stringField(detail.code, `http_${response.status}`),
      message: stringField(detail.message, response.statusText),
      existing_identifier:
        typeof detail.existing_identifier === "string" ? detail.existing_identifier : null,
      details: detail,
    };
  }

  return {
    status: response.status,
    code: `http_${response.status}`,
    message: response.statusText || "Request failed",
    details: payload,
  };
}

function queryString(values: Record<string, string | number | undefined>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined && value !== "") {
      params.set(key, String(value));
    }
  }
  const rendered = params.toString();
  return rendered ? `?${rendered}` : "";
}

function validationMessage(value: unknown): string {
  if (!isRecord(value)) {
    return "Validation error";
  }
  const location = Array.isArray(value.loc) ? value.loc.join(".") : "request";
  return `${location}: ${stringField(value.msg, "Invalid value")}`;
}

function stringField(value: unknown, fallback: string): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
