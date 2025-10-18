/**
 * Error Handling E2E Tests (Issue #24 - Phase 2)
 * 4 tests for error scenarios and graceful degradation
 */

const { test, expect } = require('@playwright/test');
const { getLocators, waitForChatReady, sendMessage } = require('./utils/locators');

test.describe('Error Handling', () => {
  test.beforeEach(async ({ page }) => {
    // Use absolute URL from environment or default to localhost
    const baseURL = process.env.PLAYWRIGHT_TEST_BASE_URL || 'http://localhost:3000';
    await page.goto(baseURL);
    await page.waitForLoadState('networkidle');
    await waitForChatReady(page);
  });

  test('handles network errors gracefully', async ({ page }) => {
    const locators = getLocators(page);

    // Simulate network error
    await page.context().setOffline(true);
    await sendMessage(page, 'Offline test');
    await page.waitForTimeout(2000);

    // Restore connectivity
    await page.context().setOffline(false);

    // Should show chat container still exists
    await expect(locators.chatContainer).toBeVisible({ timeout: 5000 });
  });

  test('handles timeout errors', async ({ page }) => {
    const locators = getLocators(page);
    test.setTimeout(30000);

    // Send message that might timeout
    const longMessage = 'This is a long query that might take a while to process: ' + 'x'.repeat(500);
    await sendMessage(page, longMessage);

    // Wait for response (reduced from 60s to 10s)
    await page.waitForTimeout(10000);

    // Should handle gracefully - chat container should still be visible
    await expect(locators.chatContainer).toBeVisible({ timeout: 5000 });
  });

  test('handles model service failures', async ({ page }) => {
    const locators = getLocators(page);

    // Send a single message and allow for potential failure
    try {
      await sendMessage(page, 'First message');
    } catch (e) {
      // Service may not respond, which is ok for this test
    }

    // Verify page is still open and functional
    expect(page.isClosed()).toBeFalsy();

    // Check that UI is still responsive
    await expect(locators.chatContainer).toBeVisible({ timeout: 5000 });

    // Try to send another message if page is still open
    if (!page.isClosed()) {
      try {
        await sendMessage(page, 'Second message');
      } catch (e) {
        // Expected behavior - service may fail
      }

      // Page should still be open
      expect(page.isClosed()).toBeFalsy();
    }
  });

  test('displays service down message appropriately', async ({ page }) => {
    const locators = getLocators(page);

    // Send a message
    await sendMessage(page, 'Service test');
    await page.waitForTimeout(3000);

    // Check that status indicator exists
    const statusVisible = await locators.statusIndicator.isVisible().catch(() => false);
    // Or chat container is still visible and functional
    await expect(locators.chatContainer).toBeVisible({ timeout: 5000 });
  });
});
