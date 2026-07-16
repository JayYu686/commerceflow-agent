import { expect, test, type APIRequestContext } from "@playwright/test";

const API_URL = process.env.E2E_API_BASE_URL ?? "http://127.0.0.1:8000";
const AS_OF = "2026-06-09T00:00:00Z";

test("质量退款在审批和执行确认后通过 MCP 完成且可幂等重放", async ({
  page,
  request,
}) => {
  const orderNo = await unusedElectronicsOrder(request);
  const message = `订单 ${orderNo} 的耳机没有声音且无法使用，我想申请质量问题退款`;

  await page.goto("/workbench");
  await page.getByLabel("用户售后诉求").fill(message);
  await page.getByRole("button", { name: "运行预览" }).click();
  await expect(page.getByText("退款审核预览", { exact: true }).first()).toBeVisible();

  const createResponsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/agent/after-sales/action-plans") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "创建动作计划" }).click();
  const created = await (await createResponsePromise).json();
  expect(created.workflow_status).toBe("awaiting_approval");

  const approvalResponse = await request.post(
    `${API_URL}/api/approvals/${created.approval_id}/decision`,
    {
      headers: { "Idempotency-Key": uniqueKey("e2e-approval") },
      data: { decision: "approve", reviewer: "playwright_reviewer" },
    },
  );
  expect(approvalResponse.ok()).toBeTruthy();

  await page.goto("/tools");
  await page.getByRole("button", { name: new RegExp(created.action_plan_id) }).click();
  const executeResponsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/action-plans/${created.action_plan_id}/execute`) &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "确认执行本地模拟工具" }).click();
  const executed = await (await executeResponsePromise).json();
  expect(executed.workflow_status).toBe("completed");
  expect(executed.execution_status).toBe("executed");
  await expect(page.getByText("已完成", { exact: true }).first()).toBeVisible();

  const replayResponsePromise = page.waitForResponse(
    (response) => response.url().endsWith(`/api/action-plans/${created.action_plan_id}/execute`),
  );
  await page.getByRole("button", { name: "使用相同幂等键重试" }).click();
  const replay = await (await replayResponsePromise).json();
  expect(replay.record_id).toBe(executed.record_id);
  expect(replay.idempotent_replay).toBe(true);
});

test("审批拒绝后动作计划保持未执行", async ({ page, request }) => {
  const orderNo = await unusedElectronicsOrder(request);
  const createdResponse = await request.post(`${API_URL}/api/agent/after-sales/action-plans`, {
    headers: { "Idempotency-Key": uniqueKey("e2e-reject-plan") },
    data: {
      message: `订单 ${orderNo} 的耳机坏了无法使用，我想退款`,
      as_of: AS_OF,
    },
  });
  expect(createdResponse.ok()).toBeTruthy();
  const created = await createdResponse.json();

  const rejected = await request.post(
    `${API_URL}/api/approvals/${created.approval_id}/decision`,
    {
      headers: { "Idempotency-Key": uniqueKey("e2e-reject-decision") },
      data: { decision: "reject", reviewer: "playwright_reviewer" },
    },
  );
  expect(rejected.ok()).toBeTruthy();

  const execute = await request.post(
    `${API_URL}/api/action-plans/${created.action_plan_id}/execute`,
    {
      headers: { "Idempotency-Key": uniqueKey("e2e-rejected-execution") },
      data: { confirm: true },
    },
  );
  expect(execute.status()).toBe(409);

  await page.goto(`/cases/${created.action_plan_id}`);
  await expect(page.getByText("已拒绝", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("未执行", { exact: true }).first()).toBeVisible();
});

async function unusedElectronicsOrder(request: APIRequestContext): Promise<string> {
  const candidates = [
    1, 6, 11, 16, 31, 36, 41, 46, 51, 61, 66, 76, 81, 86, 96, 101, 106, 111,
    116, 121, 131, 136, 141, 146, 151, 166, 171, 176, 181, 186, 191, 201, 206,
    211, 216, 226, 236, 241, 246, 251, 256, 261, 271, 276, 281, 291, 296,
  ];
  for (const index of candidates) {
    const orderNo = `CF202605${String(100000 + index)}`;
    const response = await request.get(
      `${API_URL}/api/action-plans?order_no=${orderNo}&limit=1`,
    );
    if (response.ok() && (await response.json()).action_plans.length === 0) {
      return orderNo;
    }
  }
  throw new Error("没有可用于独立 E2E 的电子产品订单；请重置演示数据后重试");
}

function uniqueKey(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
