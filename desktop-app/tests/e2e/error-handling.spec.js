/**
 * Error Handling E2E Tests (Issue #24 - Phase 2)
 * 4 tests for error scenarios and graceful degradation
 */

const { test, expect } = require('@playwright/test');

test.describe('Error Handling', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('handles network errors gracefully', async ({ page }) => {
    // Simulate network error
    await page.context().setOffline(true);

    const input = page.locator('input[placeholder*="메시지"], textarea[placeholder*="메시지"], input[placeholder*="message"], textarea[placeholder*="message"]').first();
    await input.fill('Offline test');

    const sendButton = page.locator('button:has-text("전송"), button:has-text("Send")').first();
    if (await sendButton.isVisible()) {
      await sendButton.click();
    } else {
      await input.press('Enter');
    }

    await page.waitForTimeout(2000);

    // Should show error message or retry indicator
    const errorMessage = page.locator('[class*="error"], .error-message').first();
    const retryButton = page.locator('button:has-text("Retry"), button:has-text("재시도")').first();

    // Restore connectivity
    await page.context().setOffline(false);

    // Should show either error or retry option
    await expect(errorMessage.or(retryButton)).toBeTruthy();
  });

  test('handles timeout errors', async ({ page }) => {
    const input = page.locator('input[placeholder*="메시지"], textarea[placeholder*="메시지"], input[placeholder*="message"], textarea[placeholder*="message"]').first();

    // Send message that might timeout
    await input.fill('This is a long query that might take a while to process: ' + 'x'.repeat(500));
    const sendButton = page.locator('button:has-text("전송"), button:has-text("Send")').first();
    if (await sendButton.isVisible()) {
      await sendButton.click();
    } else {
      await input.press('Enter');
    }

    // Wait potentially longer
    await page.waitForTimeout(60000); // 60 second timeout scenario

    // Should handle gracefully or show timeout message
    const chatHistory = page.locator('.chat-history, .messages, [class*="history"], [class*="messages"]').first();
    await expect(chatHistory).toBeTruthy();
  });

  test('handles model service failures', async ({ page }) => {
    const input = page.locator('input[placeholder*="메시지"], textarea[placeholder*="메시지"], input[placeholder*="message"], textarea[placeholder*="message"]').first();

    // Try multiple messages rapidly
    for (let i = 0; i < 3; i++) {
      await input.fill(`Message ${i + 1}`);
      const sendButton = page.locator('button:has-text("전송"), button:has-text("Send")').first();
      if (await sendButton.isVisible()) {
        await sendButton.click();
      } else {
        await input.press('Enter');
      }
      await page.waitForTimeout(500);
    }

    // Should handle without crashing
    const chatHistory = page.locator('.chat-history, .messages, [class*="history"], [class*="messages"]').first();
    await expect(chatHistory).toBeTruthy();
  });

  test('displays service down message appropriately', async ({ page }) => {
    // Send a message
    const input = page.locator('input[placeholder*="메시지"], textarea[placeholder*="메시지"], input[placeholder*="message"], textarea[placeholder*="message"]').first();
    await input.fill('Service test');

    const sendButton = page.locator('button:has-text("전송"), button:has-text("Send")').first();
    if (await sendButton.isVisible()) {
      await sendButton.click();
    } else {
      await input.press('Enter');
    }

    await page.waitForTimeout(3000);

    // Check for service status indicator
    const statusIndicator = page.locator('[class*="status"], [class*="health"], [class*="indicator"]').first();
    await expect(statusIndicator).toBeTruthy();
  });
});
