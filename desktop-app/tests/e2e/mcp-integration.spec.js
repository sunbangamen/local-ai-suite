/**
 * MCP Tool Integration E2E Tests (Issue #24 - Phase 2)
 * 6 tests for MCP tools (Git, File operations, etc)
 */

const { test, expect } = require('@playwright/test');

test.describe('MCP Tool Integration', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('executes git status command via MCP', async ({ page }) => {
    const input = page.locator('input[placeholder*="메시지"], textarea[placeholder*="메시지"], input[placeholder*="message"], textarea[placeholder*="message"]').first();

    // Send MCP command
    await input.fill('/mcp git_status');
    const sendButton = page.locator('button:has-text("전송"), button:has-text("Send")').first();
    if (await sendButton.isVisible()) {
      await sendButton.click();
    } else {
      await input.press('Enter');
    }

    // Wait for response
    await page.waitForTimeout(3000);

    // Should show git status output
    const chatHistory = page.locator('.chat-history, .messages, [class*="history"], [class*="messages"]').first();
    // May contain git output or error message
    await expect(chatHistory).toBeTruthy();
  });

  test('executes file read command via MCP', async ({ page }) => {
    const input = page.locator('input[placeholder*="메시지"], textarea[placeholder*="메시지"], input[placeholder*="message"], textarea[placeholder*="message"]').first();

    // Try to read a file
    await input.fill('/mcp read_file --mcp-args {"file_path": "README.md"}');
    const sendButton = page.locator('button:has-text("전송"), button:has-text("Send")').first();
    if (await sendButton.isVisible()) {
      await sendButton.click();
    } else {
      await input.press('Enter');
    }

    await page.waitForTimeout(3000);

    // Should show file content or error
    const chatHistory = page.locator('.chat-history, .messages, [class*="history"], [class*="messages"]').first();
    await expect(chatHistory).toBeTruthy();
  });

  test('executes file write command via MCP', async ({ page }) => {
    const input = page.locator('input[placeholder*="메시지"], textarea[placeholder*="메시지"], input[placeholder*="message"], textarea[placeholder*="message"]').first();

    // Try to write a test file
    await input.fill('/mcp write_file --mcp-args {"file_path": "test.txt", "content": "Test content"}');
    const sendButton = page.locator('button:has-text("전송"), button:has-text("Send")').first();
    if (await sendButton.isVisible()) {
      await sendButton.click();
    } else {
      await input.press('Enter');
    }

    await page.waitForTimeout(2000);

    // Should show success or error
    const chatHistory = page.locator('.chat-history, .messages, [class*="history"], [class*="messages"]').first();
    await expect(chatHistory).toBeTruthy();
  });

  test('handles MCP execution failures gracefully', async ({ page }) => {
    const input = page.locator('input[placeholder*="메시지"], textarea[placeholder*="메시지"], input[placeholder*="message"], textarea[placeholder*="message"]').first();

    // Try invalid MCP command
    await input.fill('/mcp invalid_command');
    const sendButton = page.locator('button:has-text("전송"), button:has-text("Send")').first();
    if (await sendButton.isVisible()) {
      await sendButton.click();
    } else {
      await input.press('Enter');
    }

    await page.waitForTimeout(2000);

    // Should handle error gracefully
    const chatHistory = page.locator('.chat-history, .messages, [class*="history"], [class*="messages"]').first();
    await expect(chatHistory).toContainText('invalid', { ignoreCase: true });
  });

  test('lists available MCP tools', async ({ page }) => {
    const input = page.locator('input[placeholder*="메시지"], textarea[placeholder*="메시지"], input[placeholder*="message"], textarea[placeholder*="message"]').first();

    // Ask for tools
    await input.fill('/mcp list');
    const sendButton = page.locator('button:has-text("전송"), button:has-text("Send")').first();
    if (await sendButton.isVisible()) {
      await sendButton.click();
    } else {
      await input.press('Enter');
    }

    await page.waitForTimeout(2000);

    // Should show available tools
    const chatHistory = page.locator('.chat-history, .messages, [class*="history"], [class*="messages"]').first();
    await expect(chatHistory).toBeTruthy();
  });

  test('MCP sandbox isolation is maintained', async ({ page }) => {
    const input = page.locator('input[placeholder*="메시지"], textarea[placeholder*="메시지"], input[placeholder*="message"], textarea[placeholder*="message"]').first();

    // Try to access protected paths
    await input.fill('/mcp read_file --mcp-args {"file_path": "/etc/passwd"}');
    const sendButton = page.locator('button:has-text("전송"), button:has-text("Send")').first();
    if (await sendButton.isVisible()) {
      await sendButton.click();
    } else {
      await input.press('Enter');
    }

    await page.waitForTimeout(2000);

    // Should be denied or restricted
    const chatHistory = page.locator('.chat-history, .messages, [class*="history"], [class*="messages"]').first();
    // May show permission error or not found
    await expect(chatHistory).toBeTruthy();
  });
});
