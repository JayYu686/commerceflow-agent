// Capture existing completed cases; does not submit claims or call a model.
const { chromium } = require("../apps/web/node_modules/@playwright/test");
const fs = require("node:fs");
const path = require("node:path");
const root = path.resolve(__dirname, "..");
const config = Object.fromEntries(fs.readFileSync(path.join(root, ".env.v2"), "utf8")
  .split(/\r?\n/).filter(l => l.includes("="))
  .map(l => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1)]));
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const output = path.join(root, "docs/screenshots/v2");
  fs.mkdirSync(output, { recursive: true });
  try {
    const hydrated = page.waitForResponse(r => r.url().endsWith("/api/session"));
    await page.goto("http://localhost:3000");
    await hydrated;
    await page.getByRole("heading", { name: "进入演示工作台" }).waitFor();
    await page.screenshot({ path: path.join(output, "login.png"), fullPage: true, caret: "initial" });
    await page.getByLabel("密码", { exact: true }).fill(config.CF_OPERATOR_PASSWORD);
    await page.getByRole("button", { name: "登录", exact: true }).click();
    await page.getByRole("heading", { name: "售后工作台", exact: true }).waitFor();
    for (const [name, order, status] of [
      ["refund-completed", process.env.CF_CAPTURE_REFUND || "CF000013", "已完成"],
      ["coupon-completed", process.env.CF_CAPTURE_COUPON || "CF000008", "已完成"],
      ["duplicate-blocked", process.env.CF_CAPTURE_COUPON || "CF000008", "未执行操作"],
    ]) {
      const cases = await (await page.request.get("http://localhost:3000/api/cases")).json();
      let selected;
      for (const item of cases) {
        if (status === "已完成" && item.status !== "completed") continue;
        if (status === "未执行操作" && item.status !== "no_action") continue;
        const view = await (await page.request.get(`http://localhost:3000/api/cases/${item.id}`)).json();
        if (view.messages.some(m => m.role === "user" && m.content.includes(order))) {
          selected = item.id; break;
        }
      }
      if (!selected) throw new Error(`No existing ${status} case for ${order}`);
      await page.locator(".case-link").filter({ hasText: selected.slice(0, 8) }).click();
      await page.locator(".main-panel .status").getByText(status, { exact: true }).waitFor();
      await page.waitForTimeout(1200);
      await page.screenshot({ path: path.join(output, name + ".png"), fullPage: true });
    }
    console.log("Captured existing demo cases in docs/screenshots/v2");
  } finally {
    await browser.close();
  }
})().catch(e => { console.error(e.message); process.exitCode = 1; });
