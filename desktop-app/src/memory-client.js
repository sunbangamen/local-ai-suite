/**
 * Memory Client - AI 메모리 시스템 클라이언트
 * 대화 저장, 검색, 통계 기능 제공
 */

const MEMORY_API_URL = 'http://localhost:8005/v1/memory';

class MemoryClient {
    constructor() {
        this.projectId = null;
        this.memoryEnabled = false;
        this.checkMemoryService();
    }

    /**
     * 메모리 서비스 상태 확인
     */
    async checkMemoryService() {
        try {
            const response = await fetch(`${MEMORY_API_URL}/health`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const data = await response.json();
                this.memoryEnabled = data.storage_available;
                this.vectorEnabled = data.vector_enabled;

                console.log('✅ Memory service available:', {
                    storage: data.storage_available,
                    vector: data.vector_enabled
                });

                // UI 업데이트
                this.updateMemoryUI(true);
                return true;
            } else {
                console.warn('⚠️ Memory service returned error status');
                this.updateMemoryUI(false);
                return false;
            }
        } catch (error) {
            console.error('❌ Memory service not available:', error.message);
            this.memoryEnabled = false;
            this.updateMemoryUI(false);
            return false;
        }
    }

    /**
     * 대화를 메모리에 저장
     */
    async saveConversation(userQuery, aiResponse, modelUsed, sessionId = null, responseTimeMs = null, tokenCount = null) {
        if (!this.memoryEnabled) {
            console.log('💡 Memory disabled, skipping save');
            return null;
        }

        try {
            const data = {
                user_query: userQuery,
                ai_response: aiResponse,
                model_used: modelUsed,
                session_id: sessionId,
                response_time_ms: responseTimeMs,
                token_count: tokenCount,
                project_path: null  // Desktop app uses default project
            };

            const response = await fetch(`${MEMORY_API_URL}/conversations`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });

            if (response.ok) {
                const result = await response.json();
                console.log(`💾 Conversation saved (ID: ${result.conversation_id}, Importance: ${result.importance_score})`);

                // UI 알림 표시
                this.showMemoryNotification(`Saved with importance ${result.importance_score}/10`);

                return result;
            } else {
                console.error('❌ Failed to save conversation:', response.status);
                return null;
            }
        } catch (error) {
            console.error('❌ Error saving conversation:', error);
            return null;
        }
    }

    /**
     * 메모리에서 대화 검색
     */
    async searchConversations(query, useVector = false, importanceMin = null, limit = 10) {
        if (!this.memoryEnabled) {
            return [];
        }

        try {
            const searchData = {
                query: query,
                use_vector: useVector && this.vectorEnabled,
                importance_min: importanceMin,
                limit: limit,
                offset: 0
            };

            const response = await fetch(`${MEMORY_API_URL}/search`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(searchData)
            });

            if (response.ok) {
                const data = await response.json();
                console.log(`🔍 Found ${data.total} conversations (${data.search_type} search)`);
                return data.results;
            } else {
                console.error('❌ Search failed:', response.status);
                return [];
            }
        } catch (error) {
            console.error('❌ Search error:', error);
            return [];
        }
    }

    /**
     * 메모리 통계 가져오기
     */
    async getStats() {
        if (!this.memoryEnabled) {
            return null;
        }

        try {
            const response = await fetch(`${MEMORY_API_URL}/stats`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const stats = await response.json();
                console.log('📊 Memory stats:', stats);
                return stats;
            } else {
                console.error('❌ Failed to get stats:', response.status);
                return null;
            }
        } catch (error) {
            console.error('❌ Stats error:', error);
            return null;
        }
    }

    /**
     * 만료된 대화 정리
     */
    async cleanup() {
        if (!this.memoryEnabled) {
            return null;
        }

        try {
            const response = await fetch(`${MEMORY_API_URL}/cleanup`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const result = await response.json();
                console.log(`🧹 Cleanup completed: ${result.deleted_count} conversations removed`);
                this.showMemoryNotification(`Cleaned up ${result.deleted_count} expired conversations`);
                return result;
            } else {
                console.error('❌ Cleanup failed:', response.status);
                return null;
            }
        } catch (error) {
            console.error('❌ Cleanup error:', error);
            return null;
        }
    }

    /**
     * 벡터 동기화 트리거
     */
    async syncVectors() {
        if (!this.memoryEnabled || !this.vectorEnabled) {
            console.log('⚠️ Vector sync not available');
            return null;
        }

        try {
            const response = await fetch(`${MEMORY_API_URL}/sync-vectors`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const result = await response.json();
                console.log(`🔄 Vector sync: ${result.synced} synced, ${result.failed} failed`);
                this.showMemoryNotification(`Vector sync: ${result.synced} synced`);
                return result;
            } else {
                console.error('❌ Vector sync failed:', response.status);
                return null;
            }
        } catch (error) {
            console.error('❌ Vector sync error:', error);
            return null;
        }
    }

    /**
     * 특정 대화 가져오기
     */
    async getConversation(conversationId) {
        if (!this.memoryEnabled) {
            return null;
        }

        try {
            const response = await fetch(`${MEMORY_API_URL}/conversation/${conversationId}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const conversation = await response.json();
                return conversation;
            } else {
                console.error('❌ Failed to get conversation:', response.status);
                return null;
            }
        } catch (error) {
            console.error('❌ Get conversation error:', error);
            return null;
        }
    }

    /**
     * 메모리 UI 업데이트
     */
    updateMemoryUI(enabled) {
        const memoryIndicator = document.getElementById('memory-indicator');
        const memoryControls = document.getElementById('memory-controls');

        if (memoryIndicator) {
            if (enabled) {
                memoryIndicator.innerHTML = '💾 <span style="color: #28a745;">Memory: ON</span>';
                memoryIndicator.title = 'Conversations are being saved to memory';
            } else {
                memoryIndicator.innerHTML = '💾 <span style="color: #dc3545;">Memory: OFF</span>';
                memoryIndicator.title = 'Memory service is unavailable';
            }
        }

        if (memoryControls) {
            memoryControls.style.display = enabled ? 'block' : 'none';
        }
    }

    /**
     * 메모리 알림 표시
     */
    showMemoryNotification(message) {
        const notification = document.createElement('div');
        notification.className = 'memory-notification';
        notification.textContent = `💾 ${message}`;
        notification.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #404040;
            color: #e0e0e0;
            padding: 12px 20px;
            border-radius: 8px;
            border: 1px solid #555;
            font-size: 14px;
            z-index: 1000;
            animation: slideIn 0.3s ease;
        `;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => {
                document.body.removeChild(notification);
            }, 300);
        }, 3000);
    }

    /**
     * 메모리 검색 UI 표시
     */
    async showMemorySearchUI() {
        const searchContainer = document.getElementById('memory-search-container');
        if (!searchContainer) {
            console.error('❌ Memory search container not found');
            return;
        }

        // 검색 폼 생성
        searchContainer.innerHTML = `
            <div class="memory-search-panel" style="
                background: #2a2a2a;
                border-radius: 10px;
                padding: 20px;
                margin-bottom: 20px;
                border: 1px solid #404040;
            ">
                <h3 style="margin-top: 0; color: #fff;">🔍 Search Memory</h3>
                <div style="display: flex; gap: 10px; margin-bottom: 15px;">
                    <input type="text" id="memory-search-input" placeholder="Search conversations..."
                        style="flex: 1; padding: 10px; background: #404040; border: 1px solid #555; color: #e0e0e0; border-radius: 6px;">
                    <button id="memory-search-btn" style="
                        padding: 10px 20px;
                        background: #0066cc;
                        color: #fff;
                        border: none;
                        border-radius: 6px;
                        cursor: pointer;
                    ">Search</button>
                </div>
                <div style="display: flex; gap: 15px; font-size: 14px;">
                    <label style="display: flex; align-items: center; gap: 5px;">
                        <input type="checkbox" id="memory-vector-search" ${this.vectorEnabled ? '' : 'disabled'}>
                        Vector Search ${!this.vectorEnabled ? '(unavailable)' : ''}
                    </label>
                    <label style="display: flex; align-items: center; gap: 5px;">
                        Min Importance:
                        <select id="memory-importance-filter" style="
                            padding: 5px;
                            background: #404040;
                            border: 1px solid #555;
                            color: #e0e0e0;
                            border-radius: 4px;
                        ">
                            <option value="">All</option>
                            <option value="5">5+</option>
                            <option value="7">7+</option>
                            <option value="9">9+</option>
                        </select>
                    </label>
                </div>
                <div id="memory-search-results" style="margin-top: 20px;"></div>
            </div>
        `;

        // 이벤트 리스너 추가
        const searchBtn = document.getElementById('memory-search-btn');
        const searchInput = document.getElementById('memory-search-input');

        const performSearch = async () => {
            const query = searchInput.value.trim();
            if (!query) return;

            const useVector = document.getElementById('memory-vector-search').checked;
            const importanceMin = document.getElementById('memory-importance-filter').value;

            const results = await this.searchConversations(
                query,
                useVector,
                importanceMin ? parseInt(importanceMin) : null,
                20
            );

            this.displaySearchResults(results);
        };

        searchBtn.addEventListener('click', performSearch);
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                performSearch();
            }
        });
    }

    /**
     * 검색 결과 표시
     */
    displaySearchResults(results) {
        const resultsContainer = document.getElementById('memory-search-results');
        if (!resultsContainer) return;

        if (results.length === 0) {
            resultsContainer.innerHTML = '<p style="color: #999;">No results found</p>';
            return;
        }

        resultsContainer.innerHTML = `
            <h4 style="color: #fff; margin-bottom: 15px;">Found ${results.length} conversations:</h4>
            ${results.map(conv => `
                <div class="memory-result" style="
                    background: #333;
                    padding: 15px;
                    margin-bottom: 10px;
                    border-radius: 8px;
                    border-left: 3px solid ${this.getImportanceColor(conv.importance_score)};
                ">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                        <span style="font-size: 12px; color: #999;">
                            ${new Date(conv.timestamp).toLocaleString()}
                        </span>
                        <span style="font-size: 12px; color: #999;">
                            Importance: ${conv.importance_score}/10 | Model: ${conv.model_used || 'N/A'}
                        </span>
                    </div>
                    <div style="margin-bottom: 8px;">
                        <strong style="color: #0066cc;">Q:</strong>
                        <span style="color: #e0e0e0;">${this.escapeHtml(conv.user_query.substring(0, 150))}${conv.user_query.length > 150 ? '...' : ''}</span>
                    </div>
                    <div>
                        <strong style="color: #28a745;">A:</strong>
                        <span style="color: #ccc;">${this.escapeHtml(conv.ai_response.substring(0, 200))}${conv.ai_response.length > 200 ? '...' : ''}</span>
                    </div>
                    ${conv.search_metadata ? `
                        <div style="margin-top: 8px; font-size: 11px; color: #777;">
                            Search type: ${conv.search_metadata.search_type} | Score: ${conv.search_metadata.combined_score?.toFixed(2) || 'N/A'}
                        </div>
                    ` : ''}
                </div>
            `).join('')}
        `;
    }

    /**
     * 중요도에 따른 색상 반환
     */
    getImportanceColor(score) {
        if (score >= 9) return '#dc3545';  // Red - Critical
        if (score >= 7) return '#ffc107';  // Yellow - High
        if (score >= 5) return '#28a745';  // Green - Medium
        return '#6c757d';  // Gray - Low
    }

    /**
     * HTML 이스케이프
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * 메모리 통계 UI 표시
     */
    async showMemoryStatsUI() {
        const stats = await this.getStats();
        if (!stats) {
            console.error('❌ Failed to get memory stats');
            return;
        }

        const statsContainer = document.getElementById('memory-stats-container');
        if (!statsContainer) {
            console.error('❌ Memory stats container not found');
            return;
        }

        statsContainer.innerHTML = `
            <div class="memory-stats-panel" style="
                background: #2a2a2a;
                border-radius: 10px;
                padding: 20px;
                margin-bottom: 20px;
                border: 1px solid #404040;
            ">
                <h3 style="margin-top: 0; color: #fff;">📊 Memory Statistics</h3>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
                    <div style="background: #333; padding: 15px; border-radius: 8px;">
                        <div style="font-size: 24px; font-weight: bold; color: #0066cc;">
                            ${stats.total_conversations}
                        </div>
                        <div style="color: #999; font-size: 14px;">Total Conversations</div>
                    </div>
                    <div style="background: #333; padding: 15px; border-radius: 8px;">
                        <div style="font-size: 24px; font-weight: bold; color: #28a745;">
                            ${stats.avg_importance.toFixed(1)}/10
                        </div>
                        <div style="color: #999; font-size: 14px;">Avg Importance</div>
                    </div>
                    <div style="background: #333; padding: 15px; border-radius: 8px;">
                        <div style="font-size: 16px; font-weight: bold; color: ${stats.vector_enabled ? '#28a745' : '#dc3545'};">
                            ${stats.vector_enabled ? '✅ Enabled' : '❌ Disabled'}
                        </div>
                        <div style="color: #999; font-size: 14px;">Vector Search</div>
                    </div>
                </div>

                <div style="margin-top: 20px;">
                    <h4 style="color: #fff; margin-bottom: 10px;">Importance Distribution</h4>
                    <div style="display: flex; flex-direction: column; gap: 5px;">
                        ${Object.entries(stats.importance_distribution || {})
                            .sort((a, b) => b[0] - a[0])
                            .map(([score, count]) => `
                                <div style="display: flex; align-items: center; gap: 10px;">
                                    <span style="min-width: 80px; color: #999;">Score ${score}:</span>
                                    <div style="flex: 1; background: #404040; border-radius: 4px; height: 20px; position: relative;">
                                        <div style="
                                            background: ${this.getImportanceColor(parseInt(score))};
                                            width: ${(count / stats.total_conversations * 100)}%;
                                            height: 100%;
                                            border-radius: 4px;
                                        "></div>
                                    </div>
                                    <span style="min-width: 60px; color: #e0e0e0;">${count} (${((count / stats.total_conversations) * 100).toFixed(1)}%)</span>
                                </div>
                            `).join('')}
                    </div>
                </div>

                <div style="margin-top: 20px;">
                    <h4 style="color: #fff; margin-bottom: 10px;">Model Usage</h4>
                    <div style="display: flex; flex-direction: column; gap: 5px;">
                        ${Object.entries(stats.model_usage || {})
                            .sort((a, b) => b[1] - a[1])
                            .map(([model, count]) => `
                                <div style="display: flex; align-items: center; gap: 10px;">
                                    <span style="min-width: 100px; color: #999;">${model}:</span>
                                    <div style="flex: 1; background: #404040; border-radius: 4px; height: 20px; position: relative;">
                                        <div style="
                                            background: #0066cc;
                                            width: ${(count / stats.total_conversations * 100)}%;
                                            height: 100%;
                                            border-radius: 4px;
                                        "></div>
                                    </div>
                                    <span style="min-width: 60px; color: #e0e0e0;">${count} (${((count / stats.total_conversations) * 100).toFixed(1)}%)</span>
                                </div>
                            `).join('')}
                    </div>
                </div>

                <div style="margin-top: 20px; display: flex; gap: 10px;">
                    <button id="memory-cleanup-btn" style="
                        padding: 10px 20px;
                        background: #dc3545;
                        color: #fff;
                        border: none;
                        border-radius: 6px;
                        cursor: pointer;
                    ">🧹 Cleanup Expired</button>
                    <button id="memory-sync-btn" ${!stats.vector_enabled ? 'disabled' : ''} style="
                        padding: 10px 20px;
                        background: ${stats.vector_enabled ? '#0066cc' : '#666'};
                        color: #fff;
                        border: none;
                        border-radius: 6px;
                        cursor: ${stats.vector_enabled ? 'pointer' : 'not-allowed'};
                    ">🔄 Sync Vectors</button>
                </div>
            </div>
        `;

        // 이벤트 리스너 추가
        document.getElementById('memory-cleanup-btn')?.addEventListener('click', async () => {
            if (confirm('Clean up expired conversations?')) {
                await this.cleanup();
                this.showMemoryStatsUI();  // 새로고침
            }
        });

        document.getElementById('memory-sync-btn')?.addEventListener('click', async () => {
            await this.syncVectors();
            this.showMemoryStatsUI();  // 새로고침
        });
    }
}

// CSS 애니메이션 추가
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// Export
if (typeof module !== 'undefined' && module.exports) {
    module.exports = MemoryClient;
}