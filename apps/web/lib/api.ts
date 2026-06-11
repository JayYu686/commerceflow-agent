import type {
  ActionPlanCreateResponse,
  AgentPreviewRequest,
  AgentPreviewResponse,
  ApiError,
  HealthResponse,
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

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
): Promise<ActionPlanCreateResponse> {
  return apiRequest<ActionPlanCreateResponse>("/api/agent/after-sales/action-plans", {
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
