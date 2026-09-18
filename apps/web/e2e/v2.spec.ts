import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

test("login layout presents roles and simulated business boundary", async ({page})=>{
  await page.goto("/");
  await expect(page.getByRole("heading",{name:"进入演示工作台"})).toBeVisible();
  await expect(page.getByLabel("工作角色")).toHaveValue("operator");
  await expect(page.getByText("所有订单、退款和优惠券均为模拟数据。")).toBeVisible();
  await page.screenshot({path:"test-results/v2-login.png",fullPage:true});
});

test("real refund approval and explicit confirmation", async ({browser})=>{
  test.skip(!process.env.CF_E2E_REAL_MODEL,"Requires the running real model and demo services");
  test.setTimeout(240000);
  const envFile=path.resolve(process.cwd(),"../../.env.v2");
  const config=Object.fromEntries(fs.readFileSync(envFile,"utf8").split(/\r?\n/).filter(l=>l.includes("=")).map(l=>[l.slice(0,l.indexOf("=")),l.slice(l.indexOf("=")+1)]));
  const operator=await browser.newContext(), reviewer=await browser.newContext();
  const op=await operator.newPage(), review=await reviewer.newPage();
  for(const [page,role] of [[op,"operator"],[review,"reviewer"]] as const){
    await page.goto("/");await page.getByLabel("工作角色").selectOption(role);
    await page.getByLabel("密码",{exact:true}).fill(config[`CF_${role.toUpperCase()}_PASSWORD`]);
    await page.getByRole("button",{name:"登录",exact:true}).click();
    await expect(page.getByRole("heading",{name:"售后工作台",exact:true})).toBeVisible({timeout:30000});
  }
  // CF000004 is a separate seeded eligible order, leaving the smoke demonstration intact.
  await op.getByLabel("售后诉求",{exact:true}).fill("订单 CF000004 的蓝牙耳机左耳没有声音，收纳包正常，请只退耳机的钱。");
  await op.getByRole("button",{name:"提交调查",exact:true}).click();
  await expect(op.getByText("等待审核",{exact:true}).first()).toBeVisible({timeout:150000});
  await review.getByRole("button").filter({has:review.getByText("CF000004",{exact:true})}).first().click();
  await review.getByLabel("已核实故障证据、商品范围及人为损坏/擅自维修等排除条款").check();
  await review.getByLabel("审核意见").fill("已核实耳机故障描述，确认排除人为损坏。");
  await review.getByRole("button",{name:"批准此版本方案"}).click();
  await expect(op.getByRole("button",{name:"确认执行 ¥199.00 模拟退款"})).toBeVisible({timeout:15000});
  await op.getByRole("button",{name:"确认执行 ¥199.00 模拟退款"}).click();
  await expect(op.getByRole("heading",{name:"执行成功",exact:true})).toBeVisible({timeout:30000});
  await op.screenshot({path:"test-results/v2-refund-completed.png",fullPage:true});
  await operator.close();await reviewer.close();
});
