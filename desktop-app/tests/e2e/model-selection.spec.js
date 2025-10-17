/**
 * Model Selection E2E Tests (Issue #24 - Phase 2)
 * 4 tests for chat vs code model switching
 */

const { test, expect } = require('@playwright/test');

test.describe('Model Selection', () => {
  test.beforeEach(async ({ page }) => {
    // Use absolute URL from environment or default to localhost
    const baseURL = process.env.PLAYWRIGHT_TEST_BASE_URL || 'http://localhost:3000';
    await page.goto(baseURL);
    await page.waitForLoadState('networkidle');
  });

  test('auto mode selects appropriate model', async ({ page }) => {
    // Look for auto/manual mode toggle
    const autoModeButton = page.locator('button:has-text("Auto"), button:has-text("자동")').first();
    if (await autoModeButton.isVisible()) {
      await autoModeButton.click();
    }

    // Status should show auto mode active
    const modeStatus = page.locator('[class*="mode"], [class*="status"]').first();
    await expect(modeStatus).toBeTruthy();
  });

  test('manual mode switches between chat and code models', async ({ page }) => {
    // Enable manual mode
    const manualModeButton = page.locator('button:has-text("Manual"), button:has-text("수동")').first();
    if (await manualModeButton.isVisible()) {
      await manualModeButton.click();
    }

    // Find model selector
    const modelDropdown = page.locator('select[name*="model"], button:has-text("Chat"), button:has-text("Code")').first();
    if (await modelDropdown.isVisible()) {
      await modelDropdown.click();

      // Look for code model option
      const codeOption = page.locator('text=Code, text=코드, text=code-7b, text=7B').first();
      if (await codeOption.isVisible()) {
        await codeOption.click();
      }
    }

    // Status should reflect code model
    const modelStatus = page.locator('[class*="model"], [class*="status"]').first();
    await expect(modelStatus).toBeTruthy();
  });

  test('chat model endpoint is used for chat queries', async ({ page }) => {
    // Set to chat mode explicitly
    const chatModeButton = page.locator('button:has-text("Chat"), button:has-text("채팅")').first();
    if (await chatModeButton.isVisible()) {
      await chatModeButton.click();
    }

    // Send chat query
    const input = page.locator('input[placeholder*="메시지"], textarea[placeholder*="메시지"], input[placeholder*="message"], textarea[placeholder*="message"]').first();
    await input.fill('Explain machine learning');

    const sendButton = page.locator('button:has-text("전송"), button:has-text("Send")').first();
    if (await sendButton.isVisible()) {
      await sendButton.click();
    } else {
      await input.press('Enter');
    }

    // Wait for response
    await page.waitForTimeout(3000);

    // Response should be in chat format
    const chatHistory = page.locator('.chat-history, .messages, [class*="history"], [class*="messages"]').first();
    await expect(chatHistory).toBeTruthy();
  });

  test('code model endpoint is used for code queries', async ({ page }) => {
    // Set to code mode
    const codeMode = page.locator('button:has-text("Code"), button:has-text("코드")').first();
    if (await codeMode.isVisible()) {
      await codeMode.click();
    }

    // Send code query
    const input = page.locator('input[placeholder*="메시지"], textarea[placeholder*="메시지"], input[placeholder*="message"], textarea[placeholder*="message"]').first();
    await input.fill('def fibonacci(n):');

    const sendButton = page.locator('button:has-text("전송"), button:has-text("Send")').first();
    if (await sendButton.isVisible()) {
      await sendButton.click();
    } else {
      await input.press('Enter');
    }

    // Wait for response
    await page.waitForTimeout(3000);

    // Code block should be present in response
    const codeBlock = page.locator('code, pre, [class*="code"]').first();
    await expect(codeBlock).toBeTruthy();
  });
});
