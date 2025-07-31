-- TrojanHorse Search Database Schema
-- Phase 3: Search Engine Foundation
-- SQLite + FTS5 for full-text search capabilities

-- Main transcripts table
CREATE TABLE IF NOT EXISTS transcripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL UNIQUE,
    date TEXT NOT NULL, -- YYYY-MM-DD format
    timestamp TEXT NOT NULL, -- ISO format: YYYY-MM-DDTHH:MM:SS
    engine TEXT, -- macwhisper, faster-whisper, etc.
    file_path TEXT NOT NULL,
    content TEXT NOT NULL,
    word_count INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Analysis results table
CREATE TABLE IF NOT EXISTS analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transcript_id INTEGER NOT NULL,
    mode TEXT NOT NULL, -- local, cloud, hybrid
    model TEXT, -- deepseek-r1:8b, gemini-2.0-flash-001, etc.
    summary TEXT,
    action_items TEXT, -- JSON array
    tags TEXT, -- JSON array
    classification TEXT, -- meeting, call, thinking, etc.
    sentiment TEXT, -- positive, neutral, negative
    confidence REAL, -- 0.0-1.0
    file_path TEXT, -- path to .analysis.md file
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (transcript_id) REFERENCES transcripts (id) ON DELETE CASCADE
);

-- FTS5 virtual table for full-text search on transcripts
CREATE VIRTUAL TABLE IF NOT EXISTS transcripts_fts USING fts5(
    filename,
    content,
    content='transcripts',
    content_rowid='id',
    tokenize='porter'
);

-- FTS5 virtual table for full-text search on analysis
CREATE VIRTUAL TABLE IF NOT EXISTS analysis_fts USING fts5(
    summary,
    action_items,
    tags,
    content='analysis',
    content_rowid='id',
    tokenize='porter'
);

-- Triggers to keep FTS5 tables in sync
CREATE TRIGGER IF NOT EXISTS transcripts_ai AFTER INSERT ON transcripts BEGIN
    INSERT INTO transcripts_fts(rowid, filename, content) 
    VALUES (new.id, new.filename, new.content);
END;

CREATE TRIGGER IF NOT EXISTS transcripts_ad AFTER DELETE ON transcripts BEGIN
    INSERT INTO transcripts_fts(transcripts_fts, rowid, filename, content) 
    VALUES('delete', old.id, old.filename, old.content);
END;

CREATE TRIGGER IF NOT EXISTS transcripts_au AFTER UPDATE ON transcripts BEGIN
    INSERT INTO transcripts_fts(transcripts_fts, rowid, filename, content) 
    VALUES('delete', old.id, old.filename, old.content);
    INSERT INTO transcripts_fts(rowid, filename, content) 
    VALUES (new.id, new.filename, new.content);
END;

CREATE TRIGGER IF NOT EXISTS analysis_ai AFTER INSERT ON analysis BEGIN
    INSERT INTO analysis_fts(rowid, summary, action_items, tags) 
    VALUES (new.id, new.summary, new.action_items, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS analysis_ad AFTER DELETE ON analysis BEGIN
    INSERT INTO analysis_fts(analysis_fts, rowid, summary, action_items, tags) 
    VALUES('delete', old.id, old.summary, old.action_items, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS analysis_au AFTER UPDATE ON analysis BEGIN
    INSERT INTO analysis_fts(analysis_fts, rowid, summary, action_items, tags) 
    VALUES('delete', old.id, old.summary, old.action_items, old.tags);
    INSERT INTO analysis_fts(rowid, summary, action_items, tags) 
    VALUES (new.id, new.summary, new.action_items, new.tags);
END;

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_transcripts_date ON transcripts(date);
CREATE INDEX IF NOT EXISTS idx_transcripts_timestamp ON transcripts(timestamp);
CREATE INDEX IF NOT EXISTS idx_transcripts_engine ON transcripts(engine);
CREATE INDEX IF NOT EXISTS idx_analysis_transcript_id ON analysis(transcript_id);
CREATE INDEX IF NOT EXISTS idx_analysis_mode ON analysis(mode);
CREATE INDEX IF NOT EXISTS idx_analysis_classification ON analysis(classification);
CREATE INDEX IF NOT EXISTS idx_transcripts_timestamp ON transcripts(timestamp);

-- Future: Vector embeddings table for semantic search (Phase 3, Task 4)
CREATE TABLE IF NOT EXISTS embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transcript_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL, -- for splitting long transcripts
    chunk_text TEXT NOT NULL,
    embedding BLOB NOT NULL, -- serialized vector
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (transcript_id) REFERENCES transcripts (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_embeddings_transcript_id ON embeddings(transcript_id);

-- Phase B: Advanced Analytics
CREATE TABLE IF NOT EXISTS analytics_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transcript_id INTEGER,
    entity_text TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    FOREIGN KEY (transcript_id) REFERENCES transcripts (id)
);

CREATE TABLE IF NOT EXISTS analytics_trends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_text TEXT NOT NULL,
    trend_score REAL NOT NULL,
    last_updated DATETIME NOT NULL
);