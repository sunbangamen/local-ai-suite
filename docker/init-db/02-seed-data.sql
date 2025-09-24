-- AI Suite Database Seed Data
-- Created: 2025-09-24
-- Purpose: Insert initial data and configuration

-- ==========================================
-- Default Collections
-- ==========================================

INSERT INTO collections (name, description, metadata) VALUES
('default', 'Default collection for general documents', '{"auto_created": true}'::jsonb),
('personal', 'Personal documents and notes', '{"private": true}'::jsonb),
('projects', 'Project-related documentation', '{"category": "work"}'::jsonb),
('knowledge', 'Knowledge base and references', '{"searchable": true}'::jsonb)
ON CONFLICT (name) DO NOTHING;

-- ==========================================
-- System Settings
-- ==========================================

INSERT INTO system_settings (key, value, description, category) VALUES
-- RAG Settings
('rag.default_collection', '"default"', 'Default collection for new documents', 'rag'),
('rag.chunk_size', '512', 'Default chunk size for document processing', 'rag'),
('rag.chunk_overlap', '100', 'Default overlap between chunks', 'rag'),
('rag.top_k_results', '4', 'Default number of results to retrieve', 'rag'),
('rag.similarity_threshold', '0.7', 'Minimum similarity score for results', 'rag'),
('rag.max_tokens', '256', 'Maximum tokens for LLM responses', 'rag'),

-- Embedding Settings
('embedding.model', '"BAAI/bge-small-en-v1.5"', 'Default embedding model', 'embedding'),
('embedding.batch_size', '64', 'Batch size for embedding generation', 'embedding'),
('embedding.max_texts', '1024', 'Maximum texts per embedding request', 'embedding'),
('embedding.max_chars', '8000', 'Maximum characters per text', 'embedding'),

-- MCP Settings
('mcp.max_execution_time', '60000', 'Maximum execution time for MCP tools (ms)', 'mcp'),
('mcp.rate_limit_requests', '100', 'Rate limit for MCP requests per minute', 'mcp'),
('mcp.log_requests', 'true', 'Whether to log MCP requests', 'mcp'),

-- Notion Settings
('notion.sync_interval', '3600', 'Sync interval for Notion pages (seconds)', 'notion'),
('notion.max_pages_per_sync', '50', 'Maximum pages to sync at once', 'notion'),

-- Web Scraping Settings
('webscrape.timeout', '30000', 'Timeout for web scraping (ms)', 'webscrape'),
('webscrape.max_content_length', '1048576', 'Maximum content length to store (bytes)', 'webscrape'),
('webscrape.screenshot_enabled', 'false', 'Whether to take screenshots', 'webscrape'),

-- System Settings
('system.version', '"1.0.0"', 'Current system version', 'system'),
('system.installation_date', to_jsonb(NOW()), 'System installation date', 'system'),
('system.debug_mode', 'false', 'Enable debug logging', 'system'),
('system.backup_retention_days', '30', 'Number of days to retain backups', 'system')

ON CONFLICT (key) DO NOTHING;

-- ==========================================
-- Sample User Preferences
-- ==========================================

INSERT INTO user_preferences (user_id, preference_key, preference_value) VALUES
('system', 'ui.theme', '"dark"'),
('system', 'search.auto_complete', 'true'),
('system', 'notifications.enabled', 'true'),
('system', 'export.default_format', '"markdown"')
ON CONFLICT (user_id, preference_key) DO NOTHING;

-- ==========================================
-- Create Views for Common Queries
-- ==========================================

-- View for document statistics
CREATE OR REPLACE VIEW document_stats AS
SELECT
    c.name as collection_name,
    COUNT(d.id) as total_documents,
    SUM(d.file_size) as total_size_bytes,
    SUM(d.chunk_count) as total_chunks,
    AVG(d.chunk_count) as avg_chunks_per_doc,
    MAX(d.upload_date) as last_upload
FROM collections c
LEFT JOIN documents d ON c.id = d.collection_id
GROUP BY c.id, c.name;

-- View for recent search activity
CREATE OR REPLACE VIEW recent_searches AS
SELECT
    query,
    collection_name,
    results_count,
    response_time_ms,
    user_feedback,
    created_at
FROM search_logs
WHERE created_at >= NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC;

-- View for MCP tool usage statistics
CREATE OR REPLACE VIEW mcp_tool_stats AS
SELECT
    tool_name,
    COUNT(*) as usage_count,
    AVG(execution_time_ms) as avg_execution_time,
    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failure_count,
    MAX(created_at) as last_used
FROM mcp_requests
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY tool_name
ORDER BY usage_count DESC;

-- ==========================================
-- Create Functions for Common Operations
-- ==========================================

-- Function to increment document count in collection
CREATE OR REPLACE FUNCTION update_collection_document_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE collections
        SET document_count = document_count + 1
        WHERE id = NEW.collection_id;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE collections
        SET document_count = document_count - 1
        WHERE id = OLD.collection_id;
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for document count
CREATE TRIGGER trigger_update_collection_count
    AFTER INSERT OR DELETE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_collection_document_count();

-- Function to clean up old search logs
CREATE OR REPLACE FUNCTION cleanup_old_search_logs()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM search_logs
    WHERE created_at < NOW() - INTERVAL '30 days';
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Function to get system health info
CREATE OR REPLACE FUNCTION get_system_health()
RETURNS JSONB AS $$
BEGIN
    RETURN jsonb_build_object(
        'collections_count', (SELECT COUNT(*) FROM collections),
        'documents_count', (SELECT COUNT(*) FROM documents),
        'chunks_count', (SELECT COUNT(*) FROM document_chunks),
        'recent_searches', (SELECT COUNT(*) FROM search_logs WHERE created_at >= NOW() - INTERVAL '1 hour'),
        'mcp_requests_today', (SELECT COUNT(*) FROM mcp_requests WHERE created_at >= CURRENT_DATE),
        'database_size', pg_size_pretty(pg_database_size(current_database())),
        'last_updated', NOW()
    );
END;
$$ LANGUAGE plpgsql;