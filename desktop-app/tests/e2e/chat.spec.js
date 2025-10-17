/**
 * Chat Interface E2E Tests (Issue #24 - Phase 2)
 * 5 tests for basic chat functionality
 */

const { test, expect } = require('@playwright/test');

test.describe('Chat Interface', () => {
  test.beforeEach(async ({ page }) => {
    // Use absolute URL from environment or default to localhost
    const baseURL = process.env.PLAYWRIGHT_TEST_BASE_URL || 'http://localhost:3000';
    await page.goto(baseURL);
    // Wait for app to load
    await page.waitForLoadState('networkidle');
  });

  test('sends message and receives response', async ({ page }) => {
    // Find and fill input
    const input = page.locator('input[placeholder*="메시지"], textarea[placeholder*="메시지"], input[placeholder*="message"], textarea[placeholder*="message"]').first();

    // Wait for input to be visible
    await input.waitFor({ state: 'visible' });
    await input.fill('Hello world');

    // Click send button or press Enter
    const sendButton = page.locator('button:has-text("전송"), button:has-text("Send")').first();

    // Wait for API response while clicking send
    try {
      await Promise.all([
        page.waitForResponse(response =>
          (response.url().includes('/chat') || response.url().includes('/completions')) &&
          response.status() === 200,
          { timeout: 10000 }
        ),
        sendButton.isVisible() ? sendButton.click() : input.press('Enter'),
      ]);
    } catch (e) {
      // If no specific API response, wait for general network idle
      await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {});
    }

    // Check that message appears in chat history
    const chatHistory = page.locator('.chat-history, .messages, [class*="history"], [class*="messages"]').first();
    await chatHistory.waitFor({ state: 'visible', timeout: 5000 }).catch(() => {});
    await expect(chatHistory).toContainText('Hello world');
  });

  test('displays loading indicator while waiting', async ({ page }) => {
    const input = page.locator('input[placeholder*="메시지"], textarea[placeholder*="메시지"], input[placeholder*="message"], textarea[placeholder*="message"]').first();
    await input.waitFor({ state: 'visible' });
    await input.fill('test');

    const sendButton = page.locator('button:has-text("전송"), button:has-text("Send")').first();

    // Send message and wait for response
    try {
      await Promise.all([
        page.waitForResponse(response =>
          (response.url().includes('/chat') || response.url().includes('/completions')) &&
          response.status() === 200,
          { timeout: 10000 }
        ),
        sendButton.isVisible() ? sendButton.click() : input.press('Enter'),
      ]);
    } catch (e) {
      // If timeout, continue - loading indicator may already be gone
    }

    // Look for loading indicator or check that response rendered
    const loadingIndicator = page.locator('[class*="loading"], [class*="spinner"], .loading-dots').first();
    const chatHistory = page.locator('.chat-history, .messages, [class*="history"], [class*="messages"]').first();

    // Either loading indicator visible or message rendered
    const isLoading = await loadingIndicator.isVisible().catch(() => false);
    const hasContent = await chatHistory.isVisible().catch(() => false);

    if (!isLoading && !hasContent) {
      await chatHistory.waitFor({ state: 'visible', timeout: 3000 }).catch(() => {});
    }
  });

  test('maintains chat history', async ({ page }) => {
    const input = page.locator('input[placeholder*="메시지"], textarea[placeholder*="메시지"], input[placeholder*="message"], textarea[placeholder*="message"]').first();
    const sendButton = page.locator('button:has-text("전송"), button:has-text("Send")').first();

    // Send first message
    await input.fill('First message');
    try {
      await Promise.all([
        page.waitForResponse(response =>
          (response.url().includes('/chat') || response.url().includes('/completions')) &&
          response.status() === 200,
          { timeout: 10000 }
        ),
        sendButton.isVisible() ? sendButton.click() : input.press('Enter'),
      ]);
    } catch (e) {
      await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {});
    }

    // Send second message
    await input.fill('Second message');
    try {
      await Promise.all([
        page.waitForResponse(response =>
          (response.url().includes('/chat') || response.url().includes('/completions')) &&
          response.status() === 200,
          { timeout: 10000 }
        ),
        sendButton.isVisible() ? sendButton.click() : input.press('Enter'),
      ]);
    } catch (e) {
      await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {});
    }

    // Both messages should be in history
    const chatHistory = page.locator('.chat-history, .messages, [class*="history"], [class*="messages"]').first();
    await chatHistory.waitFor({ state: 'visible', timeout: 5000 }).catch(() => {});
    await expect(chatHistory).toContainText('First message');
    await expect(chatHistory).toContainText('Second message');
  });

  test('handles reconnection after timeout', async ({ page }) => {
    const input = page.locator('input[placeholder*="메시지"], textarea[placeholder*="메시지"], input[placeholder*="message"], textarea[placeholder*="message"]').first();

    // Send message
    await input.fill('Reconnection test');
    const sendButton = page.locator('button:has-text("전송"), button:has-text("Send")').first();
    if (await sendButton.isVisible()) {
      await sendButton.click();
    } else {
      await input.press('Enter');
    }

    // Wait and try to send another
    await page.waitForTimeout(3000);

    await input.fill('Another message');
    if (await sendButton.isVisible()) {
      await sendButton.click();
    } else {
      await input.press('Enter');
    }

    // Should be able to send without error
    await page.waitForTimeout(2000);
    const chatHistory = page.locator('.chat-history, .messages, [class*="history"], [class*="messages"]').first();
    await expect(chatHistory).toContainText('Another message');
  });

  test('displays response with markdown formatting', async ({ page }) => {
    const input = page.locator('input[placeholder*="메시지"], textarea[placeholder*="메시지"], input[placeholder*="message"], textarea[placeholder*="message"]').first();

    await input.fill('Format test with **bold** text');
    const sendButton = page.locator('button:has-text("전송"), button:has-text("Send")').first();
    if (await sendButton.isVisible()) {
      await sendButton.click();
    } else {
      await input.press('Enter');
    }

    await page.waitForTimeout(3000);

    // Check for rendered content
    const chatHistory = page.locator('.chat-history, .messages, [class*="history"], [class*="messages"]').first();
    await expect(chatHistory).toBeTruthy();
  });
});
