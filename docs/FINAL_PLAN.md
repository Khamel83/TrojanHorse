# TrojanHorse Final Implementation Plan

## 🎯 **Refined System Architecture**

Based on user specifications:
- **Local Model**: qwen3:8b via Ollama (already available)
- **Cloud Model**: google/gemini-2.0-flash-001 via OpenRouter
- **Database**: SQLite with FTS5 (SQL Server background compatibility)
- **API Key**: OPENROUTER_API_KEY environment variable
- **Privacy**: Simplified local-first approach, minimal PII concerns
- **Maintenance**: Set-and-forget with editable prompt text files

## 🔧 **Technical Stack**

```
┌─────────────────────────────────────────────────────────────┐
│                 TrojanHorse Intelligence System             │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   analyze   │───▶│   process   │───▶│    index    │     │
│  │   .local    │    │   .gemini   │    │   .search   │     │
│  │             │    │             │    │             │     │
│  │ qwen3:8b    │    │ Flash 2.0   │    │ SQLite+FTS5 │     │
│  │ Ollama      │    │ OpenRouter  │    │ Embeddings  │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
├─────────────────────────────────────────────────────────────┤
│                   Existing Foundation                       │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   capture   │───▶│ transcribe  │───▶│ health      │     │
│  │   .audio    │    │  .whisper   │    │ .monitor    │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## 📋 **Implementation Modules**

### **Module 1: analyze_local.py**
**Purpose**: Local content processing with qwen3:8b
**Input**: Raw transcripts from daily folders
**Output**: Structured analysis with classifications and summaries

**Key Features**:
- Content classification (meeting, thinking, call, personal)
- Action item extraction
- Key point summarization
- Topic tagging
- Basic privacy filtering (optional)
- Structured JSON output

**Configuration**: `prompts/local_analysis.txt` (editable)

---

### **Module 2: process_gemini.py**
**Purpose**: Advanced analysis via Gemini Flash 2.0
**Input**: Local analysis results (sanitized)
**Output**: Strategic insights and cross-day connections

**Key Features**:
- Strategic project analysis
- Decision consistency tracking
- Long-term pattern recognition
- Cross-reference generation
- Advanced insights synthesis

**Configuration**: `prompts/gemini_analysis.txt` (editable)

---

### **Module 3: index_search.py**
**Purpose**: SQLite database with full-text and semantic search
**Input**: Processed content from both local and Gemini analysis
**Output**: Search results, timeline views, exports

**Key Features**:
- SQLite database with FTS5 full-text search
- Vector embeddings for semantic search
- Timeline and date-range queries
- Export capabilities (JSON, CSV, Markdown)
- CLI search interface

**Database Schema** (SQL Server familiar):
```sql
-- Main content table
CREATE TABLE content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    timestamp DATETIME NOT NULL,
    content_type TEXT CHECK(content_type IN ('meeting', 'thinking', 'call', 'personal')),
    transcript_file TEXT NOT NULL,
    local_summary TEXT,
    local_topics JSON,
    local_actions JSON,
    gemini_insights TEXT,
    gemini_projects JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_date (date),
    INDEX idx_content_type (content_type),
    INDEX idx_timestamp (timestamp)
);

-- Full-text search (FTS5)
CREATE VIRTUAL TABLE content_search USING fts5(
    local_summary, 
    gemini_insights,
    content=content,
    content_rowid=id
);

-- Vector embeddings for semantic search
CREATE TABLE embeddings (
    content_id INTEGER PRIMARY KEY,
    embedding BLOB,  -- Packed float array
    FOREIGN KEY(content_id) REFERENCES content(id) ON DELETE CASCADE
);
```

---

### **Module 4: workflow_cli.py**
**Purpose**: Command-line interface for queries and automation
**Input**: User queries and commands
**Output**: Search results, summaries, exports

**Key Features**:
- Natural language search queries
- Daily/weekly summary generation
- Action item tracking
- Project progress reports
- Export to various formats

---

## 🗂️ **File Structure**

```
TrojanHorse/
├── analyze_local.py          # Local qwen3:8b processing
├── process_gemini.py         # OpenRouter Gemini analysis
├── index_search.py           # SQLite database and search
├── workflow_cli.py           # Command-line interface
├── context.db                # SQLite database
├── config.yaml               # System configuration
├── prompts/                  # Editable prompt templates
│   ├── local_analysis.txt    # Local processing prompts
│   ├── gemini_analysis.txt   # Gemini processing prompts
│   └── classification.txt    # Content classification prompts
├── logs/                     # System logs
└── exports/                  # Generated exports and reports
```

## ⚙️ **Configuration System**

### **config.yaml**
```yaml
# Database Configuration
database:
  path: "context.db"
  backup_enabled: true
  backup_frequency: "weekly"
  retention_days: 365

# Local Processing (Ollama)
local:
  model: "qwen3:8b"
  endpoint: "http://localhost:11434"
  timeout: 60
  max_retries: 3

# Cloud Processing (OpenRouter)
gemini:
  model: "google/gemini-2.0-flash-001"
  api_key_env: "OPENROUTER_API_KEY"
  endpoint: "https://openrouter.ai/api/v1"
  max_tokens: 8192
  temperature: 0.1
  batch_size: 5
  cost_limit_daily: 0.20  # USD

# Processing Configuration
processing:
  auto_process_new: true
  batch_processing_time: "21:00"  # 9 PM daily
  min_transcript_length: 100  # Skip very short transcripts
  
# Search Configuration
search:
  enable_embeddings: true
  embedding_model: "all-MiniLM-L6-v2"
  max_search_results: 20
```

### **Environment Variables**
```bash
# Add to ~/.zshrc or ~/.bashrc
export OPENROUTER_API_KEY="your_api_key_here"
```

## 📝 **Editable Prompt Templates**

### **prompts/local_analysis.txt**
```
You are an AI assistant analyzing transcribed conversations for personal context capture.

Analyze the following transcript and provide structured output:

TRANSCRIPT:
{transcript}

Provide analysis in this JSON format:
{
  "content_type": "meeting|thinking|call|personal",
  "confidence": 0.0-1.0,
  "key_points": ["point 1", "point 2", "point 3"],
  "action_items": [
    {
      "item": "description",
      "priority": "high|medium|low",
      "deadline": "YYYY-MM-DD or null"
    }
  ],
  "topics": ["topic1", "topic2"],
  "decisions": ["decision 1", "decision 2"],
  "summary": "2-3 sentence summary",
  "people_mentioned": ["person1", "person2"],
  "projects_referenced": ["project1", "project2"]
}

Focus on:
- Extracting actionable items and decisions
- Identifying key topics and themes
- Providing concise but informative summaries
- Maintaining context for future reference
```

### **prompts/gemini_analysis.txt**
```
You are analyzing processed conversation summaries to provide strategic insights and cross-day pattern recognition.

CONTEXT: This is part of a personal context capture system. Look for patterns, connections, and strategic insights across conversations.

PROCESSED SUMMARIES:
{summaries}

Provide analysis in this JSON format:
{
  "strategic_insights": ["insight 1", "insight 2"],
  "project_progress": {
    "project_name": {
      "status": "progress description",
      "next_steps": ["step 1", "step 2"],
      "blockers": ["blocker 1"]
    }
  },
  "decision_tracking": [
    {
      "decision": "decision description",
      "date": "YYYY-MM-DD",
      "context": "why this decision was made",
      "follow_up_needed": true/false
    }
  ],
  "patterns_identified": ["pattern 1", "pattern 2"],
  "recommendations": ["recommendation 1", "recommendation 2"],
  "cross_references": [
    {
      "topic": "topic name",
      "related_dates": ["YYYY-MM-DD", "YYYY-MM-DD"],
      "connection": "how they relate"
    }
  ]
}

Focus on:
- Strategic thinking and long-term patterns
- Project continuity and progress tracking
- Decision consistency and follow-through
- Identifying important connections across time
```

## 🔄 **Processing Workflow**

### **Daily Automatic Processing**
1. **New Transcript Detection**: Watch for new `.txt` files in daily folders
2. **Local Analysis**: Process with qwen3:8b via Ollama
3. **Database Storage**: Store results in SQLite
4. **Batch Gemini Processing**: Evening batch for cost efficiency
5. **Index Updates**: Update search indexes and embeddings

### **Manual Processing Commands**
```bash
# Process specific transcript
python3 analyze_local.py /path/to/transcript.txt

# Process all pending transcripts
python3 analyze_local.py --batch

# Run Gemini analysis on recent content
python3 process_gemini.py --days 7

# Search content
python3 workflow_cli.py search "project budget discussion"

# Generate daily summary
python3 workflow_cli.py summary --date 2025-07-30

# Export data
python3 workflow_cli.py export --format json --date-range "2025-07-01:2025-07-31"
```

## 💰 **Cost Management**

### **Estimated Monthly Costs**
- **Local Processing**: $0 (qwen3:8b via Ollama)
- **Gemini Flash 2.0**: ~$2-4/month (based on daily usage)
- **Total**: Under $5/month target

### **Cost Controls**
- Daily spending limits in config
- Batch processing for efficiency
- Local processing for routine tasks
- Gemini only for strategic analysis

## 🚀 **Implementation Timeline**

### **Sprint 1 (Week 1)**: Foundation
- Set up analyze_local.py with qwen3:8b
- Create SQLite database schema
- Build basic processing pipeline
- Test with existing transcripts

### **Sprint 2 (Week 2)**: Intelligence Layer
- Implement process_gemini.py with OpenRouter
- Add batch processing system
- Create prompt template system
- Test end-to-end workflow

### **Sprint 3 (Week 3)**: Search & Interface
- Build index_search.py with FTS5
- Add vector embeddings for semantic search
- Create workflow_cli.py interface
- Implement export capabilities

### **Sprint 4 (Week 4)**: Integration & Polish
- Integrate with existing transcription pipeline
- Add health monitoring integration
- Create documentation and user guides
- Performance optimization and testing

## 🎛️ **Maintenance & Operations**

### **Set-and-Forget Features**
- Automatic processing of new transcripts
- Daily batch processing at 9 PM
- Weekly database backups
- Cost monitoring and alerts
- Health check integration

### **User Customization**
- Edit prompt files in `prompts/` directory
- Adjust processing schedules in `config.yaml`
- Configure cost limits and batch sizes
- Customize search result formats

### **Monitoring**
- Integration with existing health_monitor.py
- Cost tracking and daily limits
- Processing success/failure logs
- Database size and performance metrics

---

This plan provides a comprehensive, maintainable system that leverages your existing setup while adding powerful AI-driven analysis capabilities. The modular design ensures each component can be developed and tested independently, while the configuration system allows for easy customization without code changes.