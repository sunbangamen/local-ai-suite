-- AI Suite Database Schema
-- Created: 2025-09-24
-- Purpose: Initialize PostgreSQL database for RAG and MCP services

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ==========================================
-- RAG Service Tables
-- ==========================================

-- Collections table: Manage different document collections
CREATE TABLE collections (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    document_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Documents table: Track original documents
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    collection_id INTEGER REFERENCES collections(id) ON DELETE CASCADE,
    filename VARCHAR(500) NOT NULL,
    file_path TEXT NOT NULL,
    file_size BIGINT,
    mime_type VARCHAR(100),
    content_hash VARCHAR(64), -- SHA256 hash for deduplication
    upload_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    chunk_count INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending', -- pending, processing, completed, error
    error_message TEXT,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Document chunks table: Track individual text chunks
CREATE TABLE document_chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    qdrant_point_id UUID, -- Reference to Qdrant vector point
    content TEXT NOT NULL,
    chunk_index INTEGER NOT NULL, -- Position within document
    token_count INTEGER,
    embedding_model VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Search logs table: Track user queries and results
CREATE TABLE search_logs (
    id SERIAL PRIMARY KEY,
    collection_name VARCHAR(255),
    query TEXT NOT NULL,
    query_embedding_model VARCHAR(100),
    results_count INTEGER DEFAULT 0,
    top_k INTEGER DEFAULT 4,
    similarity_threshold FLOAT,
    response_time_ms INTEGER,
    llm_response_time_ms INTEGER,
    user_feedback INTEGER CHECK (user_feedback >= 1 AND user_feedback <= 5),
    feedback_comment TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- ==========================================
-- MCP Service Tables
-- ==========================================

-- MCP requests table: Track MCP tool executions
CREATE TABLE mcp_requests (
    id SERIAL PRIMARY KEY,
    session_id UUID DEFAULT uuid_generate_v4(),
    tool_name VARCHAR(100) NOT NULL,
    parameters JSONB,
    result JSONB,
    execution_time_ms INTEGER,
    status VARCHAR(20) DEFAULT 'completed', -- completed, failed, timeout
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Notion pages table: Track Notion integration
CREATE TABLE notion_pages (
    id SERIAL PRIMARY KEY,
    page_id VARCHAR(100) UNIQUE NOT NULL,
    title TEXT,
    url TEXT,
    parent_id VARCHAR(100),
    database_id VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_synced TIMESTAMP WITH TIME ZONE,
    sync_status VARCHAR(20) DEFAULT 'synced', -- synced, pending, error
    notion_created_time TIMESTAMP WITH TIME ZONE,
    notion_last_edited_time TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Web scrapes table: Track web scraping activities
CREATE TABLE web_scrapes (
    id SERIAL PRIMARY KEY,
    url TEXT NOT NULL,
    content_hash VARCHAR(64), -- SHA256 hash of content
    content_length INTEGER,
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status_code INTEGER,
    scrape_duration_ms INTEGER,
    content_type VARCHAR(100),
    title TEXT,
    description TEXT,
    screenshot_path TEXT,
    content_preview TEXT, -- First 500 chars
    metadata JSONB DEFAULT '{}'::jsonb
);

-- ==========================================
-- System Tables
-- ==========================================

-- System settings table: Store application configuration
CREATE TABLE system_settings (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    category VARCHAR(50) DEFAULT 'general',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_by VARCHAR(100) DEFAULT 'system'
);

-- User preferences table: Store user-specific settings
CREATE TABLE user_preferences (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    preference_key VARCHAR(100) NOT NULL,
    preference_value JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, preference_key)
);

-- ==========================================
-- Indexes for Performance
-- ==========================================

-- RAG indexes
CREATE INDEX idx_documents_collection_id ON documents(collection_id);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_upload_date ON documents(upload_date DESC);
CREATE INDEX idx_documents_content_hash ON documents(content_hash);

CREATE INDEX idx_chunks_document_id ON document_chunks(document_id);
CREATE INDEX idx_chunks_qdrant_point_id ON document_chunks(qdrant_point_id);

CREATE INDEX idx_search_logs_created_at ON search_logs(created_at DESC);
CREATE INDEX idx_search_logs_collection ON search_logs(collection_name);

-- MCP indexes
CREATE INDEX idx_mcp_requests_created_at ON mcp_requests(created_at DESC);
CREATE INDEX idx_mcp_requests_tool_name ON mcp_requests(tool_name);
CREATE INDEX idx_mcp_requests_session_id ON mcp_requests(session_id);

CREATE INDEX idx_notion_pages_last_synced ON notion_pages(last_synced DESC);
CREATE INDEX idx_web_scrapes_scraped_at ON web_scrapes(scraped_at DESC);
CREATE INDEX idx_web_scrapes_url_hash ON web_scrapes(url, content_hash);

-- System indexes
CREATE INDEX idx_system_settings_category ON system_settings(category);
CREATE INDEX idx_user_preferences_user_id ON user_preferences(user_id);

-- ==========================================
-- Triggers for Updated Timestamps
-- ==========================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers to relevant tables
CREATE TRIGGER update_collections_updated_at BEFORE UPDATE ON collections FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_system_settings_updated_at BEFORE UPDATE ON system_settings FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_user_preferences_updated_at BEFORE UPDATE ON user_preferences FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();