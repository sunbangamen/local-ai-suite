/**
 * Common Locators for E2E Tests
 * Centralized selectors based on actual HTML structure from desktop-app/src/index.html
 */

/**
 * Get all common locators for a page
 * @param {Page} page - Playwright page object
 * @returns {Object} Object containing all commonly used locators
 */
function getLocators(page) {
  return {
    // Chat container and messages
    chatContainer: page.locator('#chat-container'),
    userMessages: page.locator('.user-message'),
    aiMessages: page.locator('.ai-message'),
    messages: page.locator('.message'),
    messageContent: page.locator('.message-content'),
    codeBlocks: page.locator('.code'),

    // Input and send
    messageInput: page.locator('textarea#message-input'),
    sendButton: page.locator('button#send-button'),

    // Loading and status
    loadingIndicator: page.locator('#loading-indicator.loading'),
    statusIndicator: page.locator('#status-indicator'),
    currentModel: page.locator('#current-model'),

    // Model selection
    modelSelector: page.locator('#model-select'),
    modeButton: page.locator('button.mode-button'),
    autoModeButton: page.locator('button[data-mode="auto"]'),
    manualModeButton: page.locator('button[data-mode="manual"]'),

    // Error handling
    errorBanner: page.locator('[class*="error"]'),
    warningBanner: page.locator('[class*="warning"]'),
  };
}

/**
 * Wait for chat container to be ready
 * @param {Page} page - Playwright page object
 * @param {number} timeout - Timeout in ms (default 5000)
 */
async function waitForChatReady(page, timeout = 5000) {
  const locators = getLocators(page);
  await locators.chatContainer.waitFor({ state: 'attached', timeout });
}

/**
 * Get message count in chat
 * @param {Page} page - Playwright page object
 * @returns {Promise<number>} Number of messages in chat
 */
async function getMessageCount(page) {
  const locators = getLocators(page);
  return await locators.messages.count();
}

/**
 * Send a message and wait for response
 * @param {Page} page - Playwright page object
 * @param {string} message - Message to send
 * @param {number} timeout - API response timeout in ms (default 10000)
 */
async function sendMessage(page, message, timeout = 10000) {
  const locators = getLocators(page);

  await locators.messageInput.waitFor({ state: 'visible', timeout: 5000 });
  await locators.messageInput.fill(message);

  await locators.sendButton.waitFor({ state: 'visible', timeout: 5000 });
  try {
    await Promise.all([
      page.waitForResponse(response =>
        (response.url().includes('/chat') || response.url().includes('/completions')) &&
        response.status() === 200,
        { timeout }
      ),
      locators.sendButton.click(),
    ]);
  } catch (e) {
    // If no specific API response, wait for general network idle
    await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {});
  }
}

/**
 * Get current model name
 * @param {Page} page - Playwright page object
 * @returns {Promise<string>} Current model name or empty string
 */
async function getCurrentModel(page) {
  const locators = getLocators(page);
  try {
    return await locators.currentModel.textContent({ timeout: 2000 });
  } catch (e) {
    return '';
  }
}

/**
 * Check if loading indicator is visible
 * @param {Page} page - Playwright page object
 * @returns {Promise<boolean>} True if loading indicator has 'visible' class
 */
async function isLoading(page) {
  const locators = getLocators(page);
  try {
    return await locators.loadingIndicator.evaluate(el =>
      el.classList.contains('visible')
    );
  } catch (e) {
    return false;
  }
}

module.exports = {
  getLocators,
  waitForChatReady,
  getMessageCount,
  sendMessage,
  getCurrentModel,
  isLoading,
};
