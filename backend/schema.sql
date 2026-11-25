-- PulseTask PostgreSQL Database Schema for Neon
-- Run automatically by the backend server on startup

CREATE TABLE IF NOT EXISTS tasks (
    id VARCHAR(64) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT DEFAULT '',
    status VARCHAR(32) NOT NULL DEFAULT 'todo', -- 'todo', 'in_progress', 'review', 'completed'
    priority VARCHAR(16) NOT NULL DEFAULT 'medium', -- 'urgent', 'high', 'medium', 'low'
    project VARCHAR(64) NOT NULL DEFAULT 'Engineering',
    due_date DATE,
    tags JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for high performance queries
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority);
CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date);
