# TrojanHorse REST API Documentation

TrojanHorse provides a comprehensive REST API that allows external systems to integrate with your personal knowledge base. The API exposes all core functionality including processing, searching, and promoting notes to Atlas.

## 🚀 Quick Start

### Start the API Server

```bash
# Start API server (default localhost:8765)
th api

# Custom configuration
th api --host 0.0.0.0 --port 9000

# Development with auto-reload
th api --reload
```

### Interactive Documentation

- **API Docs**: http://localhost:8765/docs
- **OpenAPI Schema**: http://localhost:8765/openapi.json

## 📡 API Endpoints

### Base URL
```
http://localhost:8765
```

### Core Endpoints

#### Health Check
```http
GET /health
```

**Response:**
```json
{
  "status": "ok",
  "service": "TrojanHorse API",
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

#### Processing
```http
POST /process
```

Triggers a single processing cycle (equivalent to `th process`).

**Response:**
```json
{
  "files_scanned": 15,
  "files_processed": 8,
  "files_skipped": 7,
  "duration_seconds": 12.3,
  "errors": []
}
```

#### Embeddings
```http
POST /embed
```

Rebuilds the search index with updated embeddings (equivalent to `th embed`).

**Response:**
```json
{
  "indexed_notes": 342
}
```

#### System Statistics
```http
GET /stats
```

Returns comprehensive system statistics and configuration.

**Response:**
```json
{
  "processed_files": {
    "total_files": 1250,
    "total_size_bytes": 52428800,
    "total_size_mb": 50.0
  },
  "rag_index": {
    "total_notes": 1200,
    "categories": {
      "meeting": 45,
      "idea": 89,
      "task": 23,
      "email": 156
    },
    "projects": {
      "project-x": 34,
      "warn_dashboard": 12,
      "none": 1104
    }
  },
  "config": {
    "vault_root": "/Users/user/WorkVault",
    "capture_dirs": ["/Users/user/WorkVault/Inbox"],
    "llm_model": "google/gemini-2.5-flash-lite-001",
    "embedding_model": "text-embedding-3-small"
  }
}
```

### Notes Management

#### List Notes
```http
GET /notes?q=search&category=meeting&project=project-x&limit=50&offset=0
```

**Query Parameters:**
- `q` (string, optional): Search query
- `category` (string, optional): Filter by category
- `project` (string, optional): Filter by project
- `workspace` (string, optional): Filter by workspace
- `limit` (integer, default=50): Maximum results
- `offset` (integer, default=0): Pagination offset

**Response:**
```json
{
  "items": [
    {
      "id": "2024-01-15-143000-project-sync",
      "source": "drafts",
      "raw_type": "meeting_transcript",
      "class_type": "work",
      "category": "meeting",
      "project": "project-x",
      "created_at": "2024-01-15T14:30:00.000Z",
      "processed_at": "2024-01-15T14:35:00.000Z",
      "summary": "Weekly project sync with team. Discussed timeline and blockers.",
      "tags": ["project-x", "sync", "timeline"],
      "original_path": "/Users/user/WorkVault/Inbox/2024-01-15-143000-project-sync.md",
      "dest_path": "/Users/user/WorkVault/Processed/work/meetings/2024/2024-01-15-project-sync.md"
    }
  ],
  "total": 1
}
```

#### Get Specific Note
```http
GET /notes/{note_id}
```

**Response:**
```json
{
  "meta": {
    "id": "2024-01-15-143000-project-sync",
    "source": "drafts",
    "raw_type": "meeting_transcript",
    "class_type": "work",
    "category": "meeting",
    "project": "project-x",
    "created_at": "2024-01-15T14:30:00.000Z",
    "processed_at": "2024-01-15T14:35:00.000Z",
    "summary": "Weekly project sync with team...",
    "tags": ["project-x", "sync"],
    "original_path": "...",
    "dest_path": "..."
  },
  "content": {
    "body": "# Project Sync Meeting\n\n## Attendees\n- John (PM)\n- Sarah (Dev)\n- Mike (Designer)\n\n## Discussion\nDiscussed the Q1 roadmap and timeline...",
    "frontmatter": {
      "title": "Project Sync Meeting",
      "meeting_type": "weekly_sync",
      "duration_minutes": 45
    }
  }
}
```

### Search & Query

#### Ask Question (RAG)
```http
POST /ask
```

**Request Body:**
```json
{
  "question": "What did we decide about the project timeline?",
  "top_k": 8,
  "workspace": "work",
  "category": "meeting"
}
```

**Response:**
```json
{
  "answer": "Based on the meeting notes, the team decided to extend the project timeline by 2 weeks due to unexpected technical challenges with the payment integration. The new target date is March 15th, with a review checkpoint on February 28th.",
  "sources": [
    {
      "note_id": "2024-01-15-143000-project-sync",
      "title": "Project Sync Meeting",
      "relevance_score": 0.89
    }
  ],
  "contexts": [
    {
      "note_id": "2024-01-15-143000-project-sync",
      "path": "/Users/user/WorkVault/Processed/work/meetings/2024/2024-01-15-project-sync.md",
      "similarity": 0.89,
      "content_snippet": "## Timeline Decision\nAfter discussing the payment integration challenges, we agreed to extend the timeline by 2 weeks..."
    }
  ]
}
```

### Atlas Integration

#### Promote Notes to Atlas
```http
POST /promote
```

Prepares notes for export to Atlas long-term library.

**Request Body:**
```json
{
  "note_ids": ["note1", "note2", "note3"]
}
```

**Response:**
```json
{
  "items": [
    {
      "id": "note1",
      "path": "/Users/user/WorkVault/Processed/work/ideas/2024/note1.md",
      "title": "New Feature Idea: Dashboard Analytics",
      "source": "drafts",
      "raw_type": "idea",
      "class_type": "work",
      "category": "idea",
      "project": "dashboard",
      "tags": ["analytics", "dashboard", "feature"],
      "created_at": "2024-01-15T09:00:00.000Z",
      "updated_at": "2024-01-15T09:05:00.000Z",
      "summary": "Proposed adding real-time analytics dashboard to track user engagement",
      "body": "# Dashboard Analytics Feature\n\n## Overview\nAdd real-time analytics to show user engagement metrics...",
      "frontmatter": {
        "priority": "high",
        "estimated_effort": "2 weeks"
      }
    }
  ]
}
```

## 🔧 Configuration

### Environment Variables

```bash
# Core configuration
export WORKVAULT_ROOT="/Users/user/WorkVault"
export TROJANHORSE_STATE_DIR="/Users/user/.trojanhorse"

# Atlas integration (optional)
export ATLAS_API_URL="http://localhost:8787"
export ATLAS_API_KEY="your-atlas-api-key"

# LLM configuration
export OPENROUTER_API_KEY="your-openrouter-key"
export OPENROUTER_MODEL="google/gemini-2.5-flash-lite-001"

# Embedding configuration
export EMBEDDING_API_KEY="your-embedding-key"
export EMBEDDING_MODEL_NAME="text-embedding-3-small"
```

### API Server Options

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | `127.0.0.1` | Host to bind server to |
| `--port` | `8765` | Port to bind server to |
| `--reload` | `false` | Enable auto-reload for development |

## 🔌 Integration Examples

### Python Client
```python
import requests

class TrojanHorseClient:
    def __init__(self, base_url="http://localhost:8765"):
        self.base_url = base_url.rstrip('/')

    def health_check(self):
        response = requests.get(f"{self.base_url}/health")
        return response.json()

    def process_files(self):
        response = requests.post(f"{self.base_url}/process")
        return response.json()

    def search_notes(self, query=None, category=None, limit=50):
        params = {"limit": limit}
        if query:
            params["q"] = query
        if category:
            params["category"] = category

        response = requests.get(f"{self.base_url}/notes", params=params)
        return response.json()["items"]

    def ask_question(self, question, top_k=8):
        response = requests.post(
            f"{self.base_url}/ask",
            json={"question": question, "top_k": top_k}
        )
        return response.json()

# Usage
client = TrojanHorseClient()

# Check health
health = client.health_check()
print(f"API Status: {health['status']}")

# Process new files
result = client.process_files()
print(f"Processed {result['files_processed']} files")

# Search for meeting notes
meetings = client.search_notes(category="meeting")
print(f"Found {len(meetings)} meetings")

# Ask questions
answer = client.ask_question("What are the upcoming deadlines?")
print(f"Answer: {answer['answer']}")
```

### JavaScript Client
```javascript
class TrojanHorseClient {
    constructor(baseUrl = 'http://localhost:8765') {
        this.baseUrl = baseUrl.replace(/\/$/, '');
    }

    async healthCheck() {
        const response = await fetch(`${this.baseUrl}/health`);
        return await response.json();
    }

    async processFiles() {
        const response = await fetch(`${this.baseUrl}/process`, {
            method: 'POST'
        });
        return await response.json();
    }

    async searchNotes(filters = {}) {
        const params = new URLSearchParams(filters);
        const response = await fetch(`${this.baseUrl}/notes?${params}`);
        const data = await response.json();
        return data.items;
    }

    async askQuestion(question, topK = 8) {
        const response = await fetch(`${this.baseUrl}/ask`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                question: question,
                top_k: topK
            })
        });
        return await response.json();
    }
}

// Usage
const client = new TrojanHorseClient();

// Check health
client.healthCheck().then(health => {
    console.log(`API Status: ${health.status}`);
});

// Search notes
client.searchNotes({ category: 'idea', limit: 10 })
    .then(notes => {
        console.log(`Found ${notes.length} ideas`);
        notes.forEach(note => {
            console.log(`- ${note.title}: ${note.summary}`);
        });
    });
```

### Shell Scripts
```bash
#!/bin/bash
# Process and search workflow

API_BASE="http://localhost:8765"

echo "🔍 Processing new files..."
PROCESS_RESULT=$(curl -s -X POST "$API_BASE/process")
echo "✅ Processing complete: $(echo $PROCESS_RESULT | jq -r '.files_processed') files processed"

echo "🔍 Searching for recent meeting notes..."
MEETINGS=$(curl -s "$API_BASE/notes?category=meeting&limit=5")
echo "📝 Found $(echo $MEETINGS | jq '.items | length') recent meetings"

echo "❓ Asking about project status..."
ANSWER=$(curl -s -X POST "$API_BASE/ask" \
    -H "Content-Type: application/json" \
    -d '{"question": "What is the current project status?"}')
echo "💬 Answer: $(echo $ANSWER | jq -r '.answer')"
```

## 🛡️ Security & Best Practices

### Authentication
- API binds to `127.0.0.1` by default (localhost only)
- Use `--host 0.0.0.0` carefully in production
- Consider reverse proxy with SSL for production deployments

### Rate Limiting
- No built-in rate limiting (designed for local use)
- Implement application-level limiting for production

### Error Handling
```python
try:
    response = requests.post(f"{base_url}/ask", json=...)
    response.raise_for_status()
    data = response.json()
except requests.exceptions.HTTPError as e:
    print(f"HTTP Error: {e}")
except requests.exceptions.ConnectionError:
    print("Connection failed - is TrojanHorse API running?")
except requests.exceptions.Timeout:
    print("Request timed out")
except requests.exceptions.RequestException as e:
    print(f"Request error: {e}")
```

### Data Validation
```python
from pydantic import BaseModel, validator
from typing import Optional, List

class AskRequest(BaseModel):
    question: str
    top_k: int = 8
    workspace: Optional[str] = None
    category: Optional[str] = None
    project: Optional[str] = None

    @validator('top_k')
    def validate_top_k(cls, v):
        if v < 1 or v > 20:
            raise ValueError('top_k must be between 1 and 20')
        return v
```

## 🔍 Monitoring & Debugging

### Health Monitoring
```bash
# Simple health check
curl -f http://localhost:8765/health || echo "API DOWN"

# Comprehensive health
curl -s http://localhost:8765/stats | jq '.processed_files.total_files'
```

### Log Analysis
```bash
# API server logs (if running with th api)
tail -f ~/.trojanhorse/logs/api.log

# Processing logs
tail -f ~/.trojanhorse/logs/processing.log
```

### Performance Monitoring
```bash
# Test API response time
time curl -s http://localhost:8765/health > /dev/null

# Test with larger queries
time curl -s -X POST http://localhost:8765/ask \
    -H "Content-Type: application/json" \
    -d '{"question": "What are the main project priorities?"}' > /dev/null
```

## 🚨 Troubleshooting

### Common Issues

**API won't start:**
- Check if port is in use: `lsof -i :8765`
- Verify dependencies: `pip install -r requirements.txt`
- Check configuration: `th status`

**Empty search results:**
- Run `th embed` to rebuild index
- Check if files are processed: `th status`
- Verify query format and filters

**Connection refused:**
- Ensure API server is running: `th api`
- Check if correct host/port is used
- Verify firewall settings

**Promotion to Atlas fails:**
- Check Atlas API status: `curl http://localhost:8787/health`
- Verify environment variables: `env | grep ATLAS`
- Check API key configuration

### Debug Mode
```bash
# Start API with debug logging
th api --log-level debug

# Or set environment variable
export TROJANHORSE_LOG_LEVEL=debug
th api
```

### API Testing with curl
```bash
# Health check
curl http://localhost:8765/health

# Test processing
curl -X POST http://localhost:8765/process

# Test search with filters
curl "http://localhost:8765/notes?category=meeting&limit=3"

# Test question answering
curl -X POST http://localhost:8765/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What meetings did I have this week?"}'

# Test promotion
curl -X POST http://localhost:8765/promote \
  -H "Content-Type: application/json" \
  -d '{"note_ids": ["test-note-id"]}'
```

## 📚 Additional Resources

- **CLI Commands**: `th --help`
- **Configuration**: See `.env.template`
- **Architecture**: See `docs/ARCHITECTURE.md`
- **Atlas Integration**: See Atlas API documentation
- **Examples**: See `examples/` directory

---

*For questions or issues, please refer to the main README.md or create an issue on GitHub.*