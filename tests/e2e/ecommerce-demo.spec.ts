import { expect, test } from "@playwright/test";

const baseURL = process.env.APP_BASE_URL ?? "http://localhost:3000";
const coreServiceBaseURL = process.env.CORE_SERVICE_BASE_URL ?? "http://localhost:4000";
const password = process.env.TEST_USER_PASSWORD ?? "Passw0rd!ForTests";

test.describe("ecommerce demo critical browser flows", () => {
  test.beforeEach(async ({ page, request }) => {
    const token = process.env.TEST_ADMIN_TOKEN;
    if (token) {
      await request.post(`${coreServiceBaseURL}/api/test/reset`, {
        headers: { authorization: `Bearer ${token}` },
      });
      await request.post(`${coreServiceBaseURL}/api/test/seed`, {
        headers: { authorization: `Bearer ${token}` },
        data: {
          products: "fashion-minimal",
          users: true,
          orders: true,
          embeddings: true,
        },
      });
    }
    await page.goto(baseURL);
  });

  test("guest browses, filters, searches, opens product detail, and is asked to sign in before adding to bag", async ({ page }) => {
    await page.goto(`${baseURL}/products`);
    await expect(page.getByRole("heading", { name: /^products catalogue$/i })).toBeVisible();

    await page.getByRole("searchbox").fill("black shoes");
    await page.getByRole("button", { name: /^search$/i }).click();
    await expect(page.getByText(/black|shoes/i).first()).toBeVisible();

    await page.getByRole("checkbox", { name: /^men$/i }).check();
    await page.getByRole("checkbox", { name: /^black$/i }).check();
    await expect(page).toHaveURL(/gender|baseColour|color/i);

    await page.getByRole("link", { name: /shoe|product/i }).first().click();
    await expect(page.getByRole("button", { name: /add to bag/i })).toBeVisible();
    await page.getByRole("button", { name: /add to bag/i }).click();
    await expect(page).toHaveURL(/login/);
  });

  test("user registers, adds to bag, and demo checkout creates an order", async ({ page }) => {
    const email = `e2e-checkout-${Date.now()}@example.test`;
    await registerViaUi(page, email);

    await page.goto(`${baseURL}/products`);
    await page.getByRole("button", { name: /add to bag/i }).first().click();
    await expect(page.getByText(/added to bag/i)).toBeVisible();
    await page.getByRole("link", { name: /bag/i }).click();
    await expect(page.getByText(/subtotal|total/i)).toBeVisible();

    await page.getByRole("button", { name: /checkout/i }).click();
    await page.getByLabel(/name/i).fill("E2E Shopper");
    await page.getByLabel(/address|line 1/i).fill("1 Demo Street");
    await page.getByLabel(/city/i).fill("Bengaluru");
    await page.getByLabel(/state|region/i).fill("KA");
    await page.getByLabel(/postal|zip/i).fill("560001");
    await page.getByLabel(/phone/i).fill("+919999999999");
    await page.getByRole("radio", { name: /demo/i }).check();
    await page.getByRole("button", { name: /place order/i }).click();

    await expect(page.getByText(/ORD-/)).toBeVisible();
    await expect(page.getByText(/order confirmed|thank you/i)).toBeVisible();
  });

  test("single search button returns hybrid results with visible active filters", async ({ page }) => {
    await page.goto(`${baseURL}/products`);
    await page.getByRole("searchbox").fill("lightweight black running shoes for men under 3000");
    await page.getByRole("button", { name: /^search$/i }).click();

    await expect(page.getByText(/running|black|shoes/i).first()).toBeVisible();
    await expect(page.getByText(/men|under|3000|black/i).first()).toBeVisible();
  });

  test("shopping assistant recommends products and adds to cart after confirmation", async ({ page }) => {
    const email = `e2e-assistant-${Date.now()}@example.test`;
    await registerViaUi(page, email);

    await page.goto(`${baseURL}/products`);
    await page.getByRole("button", { name: /assistant|chat/i }).click();
    await page.getByRole("textbox", { name: /message|ask/i }).fill(
      "Find black casual shoes under 3000 and add the best one to my cart.",
    );
    await page.keyboard.press("Enter");

    await expect(page.getByText(/recommend|option|match/i).first()).toBeVisible();
    await page.getByRole("button", { name: /confirm|add to cart|confirm/i }).click();
    await expect(page.getByText(/added/i)).toBeVisible();
  });

  test("support agent uses mandatory MCP flow to create a return request", async ({ page }) => {
    const email = `e2e-return-${Date.now()}@example.test`;
    await registerViaUi(page, email);
    await placeOrderViaUi(page);

    await page.goto(`${baseURL}/support`);
    await page.getByRole("textbox", { name: /message|ask/i }).fill(
      "I want to return the first item from my latest order. Check eligibility and prepare the return.",
    );
    await page.keyboard.press("Enter");

    await expect(page.getByText(/eligible|return window|policy/i)).toBeVisible();
    await page.getByLabel(/reason/i).fill("Size issue");
    await page.getByLabel(/condition/i).selectOption({ label: "Unused" });
    await page.getByRole("button", { name: /confirm|create return/i }).click();
    await expect(page.getByText(/RET-/)).toBeVisible();
  });

  test("admin console shows provider config, activity funnel, and MCP readiness", async ({ page }) => {
    await page.goto(`${baseURL}/admin`);

    await expect(page.getByText(/python/i)).toBeVisible();
    await expect(page.getByText(/fastapi/i)).toBeVisible();
    await expect(page.getByText(/gpt-5\.4/i)).toBeVisible();
    await expect(page.getByText(/nomic-embed-text|voyage-4/i)).toBeVisible();
    await expect(page.getByText(/local_filesystem|local filesystem/i)).toBeVisible();
    await expect(page.getByText(/MCP/i)).toBeVisible();
    await expect(page.getByText(/ready|healthy/i)).toBeVisible();
    await expect(page.getByText(/activity|funnel/i)).toBeVisible();
  });
});

async function registerViaUi(page: import("@playwright/test").Page, email: string) {
  await page.goto(`${baseURL}/register`);
  await page.getByLabel(/name/i).fill("E2E Shopper");
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/^password$/i).fill(password);
  await page.getByRole("button", { name: /register|create account/i }).click();
  await expect(page.getByRole("link", { name: /^account$/i })).toBeVisible();
}

async function placeOrderViaUi(page: import("@playwright/test").Page) {
  await page.goto(`${baseURL}/products`);
  await page.getByRole("button", { name: /add to bag/i }).first().click();
  await expect(page.getByText(/added to bag/i)).toBeVisible();
  await page.goto(`${baseURL}/checkout`);
  await page.getByLabel(/name/i).fill("E2E Shopper");
  await page.getByLabel(/address|line 1/i).fill("1 Demo Street");
  await page.getByLabel(/city/i).fill("Bengaluru");
  await page.getByLabel(/state|region/i).fill("KA");
  await page.getByLabel(/postal|zip/i).fill("560001");
  await page.getByLabel(/phone/i).fill("+919999999999");
  await page.getByRole("radio", { name: /demo/i }).check();
  await page.getByRole("button", { name: /place order/i }).click();
  await expect(page.getByText(/ORD-/)).toBeVisible();
}
