# Implementation Tasks

## Phase 1: analyze.local - Local Privacy-First Processing

### **Task 1.1: Environment Setup**
**Priority**: High | **Estimated Time**: 2 hours

- [ ] Install and configure Ollama with qwen3:8b model
- [ ] Test model loading and basic inference
- [ ] Verify memory usage on 16GB M1 MacBook Pro
- [ ] Create model performance benchmarks
- [ ] Document optimal inference parameters

**Acceptance Criteria**:
- qwen3:8b loads successfully and uses <8GB RAM
- Basic text processing completes in <30 seconds for 1000 words
- Model responds consistently to privacy filtering prompts

**Implementation Notes**:
```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull qwen3:8b model
ollama pull qwen3:8b

# Test model
ollama run qwen3:8b "Classify this text as work or personal: I had a meeting about the quarterly budget."
```

---

### **Task 1.2: Content Classification System**
**Priority**: High | **Estimated Time**: 6 hours

- [ ] Design content type taxonomy (meeting, thinking, call, dictation, personal)
- [ ] Create prompt templates for classification
- [ ] Implement confidence scoring for classifications
- [ ] Build unit tests with sample transcripts
- [ ] Optimize prompts for accuracy and speed

**Acceptance Criteria**:
- >85% accuracy on test dataset of varied content types
- Classification completes in <5 seconds per transcript
- Confidence scores correlate with actual accuracy

**Implementation Structure**:
```python
class ContentClassifier:
    def __init__(self, model_endpoint="http://localhost:11434"):
        self.model = "qwen3:8b"
        self.endpoint = model_endpoint
    
    def classify_content(self, transcript: str) -> ContentClassification:
        """
        Returns: ContentClassification with:
        - content_type: Enum[MEETING, THINKING, CALL, DICTATION, PERSONAL]
        - confidence: float 0-1
        - context_tags: List[str]
        - urgency_level: int 1-5
        """
```

---

### **Task 1.3: Privacy Protection Engine**
**Priority**: Critical | **Estimated Time**: 8 hours

- [ ] Build PII detection patterns (names, phone numbers, emails, addresses)
- [ ] Implement sensitive topic identification
- [ ] Create privacy scoring algorithm (1-10 scale)
- [ ] Design sanitization methods (redaction, anonymization, context preservation)
- [ ] Build comprehensive test suite with known PII examples

**Acceptance Criteria**:
- >95% PII detection accuracy on test dataset
- Zero false negatives on critical PII (SSN, passwords, phone numbers)
- Sanitized text preserves meaningful context
- Privacy scores accurately reflect sensitivity levels

**Privacy Patterns**:
```python
PII_PATTERNS = {
    'phone': r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
    'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
    'names': r'\b[A-Z][a-z]+\s[A-Z][a-z]+\b',  # Enhanced with NER
    'addresses': r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr)\b'
}
```

---

### **Task 1.4: Content Processing Pipeline**
**Priority**: High | **Estimated Time**: 6 hours

- [ ] Implement key point extraction using structured prompts
- [ ] Build action item identification system
- [ ] Create decision and conclusion tracking
- [ ] Design topic and project tagging system
- [ ] Implement structured JSON output format

**Acceptance Criteria**:
- Extracts 3-5 key points per 5-minute transcript
- Identifies 80%+ of explicit action items
- Topics are relevant and consistently labeled
- JSON output validates against defined schema

**Output Schema**:
```json
{
  "timestamp": "2025-07-30T14:30:00Z",
  "content_type": "MEETING",
  "confidence": 0.92,
  "privacy_score": 7,
  "key_points": ["Budget approval needed", "Q3 targets discussion"],
  "action_items": [
    {
      "item": "Send budget proposal to finance team",
      "assignee": "REDACTED",
      "deadline": "2025-08-01"
    }
  ],
  "topics": ["budget", "quarterly-planning", "finance"],
  "decisions": ["Approved 15% budget increase for marketing"],
  "sanitized_summary": "Team discussed quarterly budget allocation and growth targets for next quarter."
}
```

---

### **Task 1.5: Integration with Existing System**
**Priority**: Medium | **Estimated Time**: 4 hours

- [ ] Modify transcribe.py to trigger local analysis
- [ ] Create file watching system for new transcripts
- [ ] Implement batch processing for historical transcripts
- [ ] Add processed content to daily folder structure
- [ ] Update health monitoring to include local processing

**Acceptance Criteria**:
- New transcripts automatically trigger local processing
- Processed content appears in daily folders within 60 seconds
- Health monitor shows local processing status
- No impact on existing transcription pipeline

**Integration Points**:
```python
# In transcribe.py
def post_process_transcript(self, transcript_file: Path) -> None:
    # Existing post-processing...
    
    # Trigger local analysis
    from analyze_local import LocalAnalyzer
    analyzer = LocalAnalyzer()
    analyzer.process_transcript_async(transcript_file)
```

---

## Phase 2: process.gemini - Cloud Intelligence

### **Task 2.1: OpenRouter API Integration**
**Priority**: High | **Estimated Time**: 4 hours

- [ ] Set up OpenRouter API client with google/gemini-2.0-flash-001
- [ ] Implement authentication and error handling
- [ ] Build rate limiting and cost monitoring
- [ ] Create retry logic with exponential backoff
- [ ] Test API integration with sample requests

**Acceptance Criteria**:
- API client successfully authenticates and makes requests
- Rate limiting prevents API overuse
- Cost tracking stays under $5/month target
- Handles network failures gracefully

**Configuration**:
```python
OPENROUTER_CONFIG = {
    "api_base": "https://openrouter.ai/api/v1",
    "model": "google/gemini-2.0-flash-001",
    "max_tokens": 8192,
    "temperature": 0.1,
    "rate_limit": 10,  # requests per minute
    "cost_limit_daily": 0.20  # USD
}
```

---

### **Task 2.2: Strategic Analysis Engine**
**Priority**: High | **Estimated Time**: 6 hours

- [ ] Design prompts for project progress tracking
- [ ] Implement decision consistency analysis
- [ ] Build goal progress identification system
- [ ] Create strategic recommendation generator
- [ ] Develop pattern recognition for long-term insights

**Acceptance Criteria**:
- Identifies project updates across multiple conversations
- Flags inconsistent decisions for review
- Generates actionable strategic recommendations
- Tracks goal progress over time

---

### **Task 2.3: Batch Processing System**
**Priority**: Medium | **Estimated Time**: 4 hours

- [ ] Implement daily batch processing for cost efficiency
- [ ] Create queue system for pending analysis
- [ ] Build batch optimization (group similar content)
- [ ] Add processing status tracking
- [ ] Implement manual trigger for immediate analysis

**Acceptance Criteria**:
- Daily batches process automatically at scheduled time
- Manual trigger works for urgent analysis
- Batch processing reduces API costs by 60%+
- Status tracking shows progress and completion

---

## Phase 3: index.search - Memory and Retrieval

### **Task 3.1: Database Design and Setup**
**Priority**: High | **Estimated Time**: 6 hours

- [ ] Design SQLite schema for content storage
- [ ] Implement FTS5 full-text search indexes
- [ ] Create embedding storage for semantic search
- [ ] Build database migration system
- [ ] Add data integrity and backup features

**Acceptance Criteria**:
- Database handles 10,000+ content items efficiently
- Full-text search returns results in <500ms
- Database migrations work without data loss
- Automated backups run weekly

---

### **Task 3.2: Embedding Generation System**
**Priority**: Medium | **Estimated Time**: 4 hours

- [ ] Integrate sentence-transformers for embeddings
- [ ] Implement batch embedding generation
- [ ] Create vector similarity search
- [ ] Build embedding update system for new content
- [ ] Optimize embedding storage and retrieval

**Acceptance Criteria**:
- Embeddings generate for all processed content
- Semantic search finds relevant content by concept
- Vector search completes in <1 second
- Embedding updates happen automatically

---

### **Task 3.3: Search Interface Development**
**Priority**: Medium | **Estimated Time**: 6 hours

- [ ] Build command-line search interface
- [ ] Implement query parsing and filtering
- [ ] Create timeline and date-range search
- [ ] Add export functionality (JSON, CSV, Markdown)
- [ ] Build related content suggestions

**Acceptance Criteria**:
- CLI search interface is intuitive and fast
- Complex queries work with filters and date ranges
- Export functions produce clean, usable output
- Related content suggestions are relevant

---

## Phase 4: integrate.workflow - Application Layer

### **Task 4.1: Context-Aware Query System**
**Priority**: Low | **Estimated Time**: 4 hours

- [ ] Build natural language query processor
- [ ] Implement context building for responses
- [ ] Create historical perspective system
- [ ] Add conversation thread tracking
- [ ] Build query result ranking system

---

### **Task 4.2: Proactive Assistance Features**
**Priority**: Low | **Estimated Time**: 6 hours

- [ ] Implement daily summary generation
- [ ] Create weekly pattern analysis
- [ ] Build reminder system for follow-ups
- [ ] Add notification system for insights
- [ ] Create automated report generation

---

### **Task 4.3: External Tool Integration**
**Priority**: Low | **Estimated Time**: 6 hours

- [ ] Build Obsidian note export system
- [ ] Create Notion database integration
- [ ] Implement task manager connections
- [ ] Add calendar integration for context
- [ ] Build custom webhook system

---

## Implementation Priority Matrix

### **Sprint 1 (Immediate - Week 1-2)**
1. Task 1.1: Environment Setup (Critical Path)
2. Task 1.3: Privacy Protection Engine (Security Critical)
3. Task 1.2: Content Classification System
4. Task 1.4: Content Processing Pipeline

### **Sprint 2 (Week 3-4)**
1. Task 1.5: Integration with Existing System
2. Task 2.1: OpenRouter API Integration
3. Task 2.2: Strategic Analysis Engine
4. Task 2.3: Batch Processing System

### **Sprint 3 (Week 5-6)**
1. Task 3.1: Database Design and Setup
2. Task 3.2: Embedding Generation System
3. Task 3.3: Search Interface Development

### **Sprint 4+ (Week 7+)**
1. Task 4.1: Context-Aware Query System
2. Task 4.2: Proactive Assistance Features
3. Task 4.3: External Tool Integration

---

## Testing Strategy

### **Unit Testing Requirements**
- All privacy filtering functions must have >95% test coverage
- Content classification tested with diverse sample data
- API integration tested with mock responses
- Database operations tested with transaction rollback

### **Integration Testing**
- End-to-end pipeline testing with sample transcripts
- Performance testing with realistic data volumes
- Cost monitoring testing with API simulation
- Error handling testing with network failures

### **Privacy Testing**
- PII detection testing with known sensitive data
- Sanitization testing to ensure context preservation
- Privacy score validation with manual review
- Audit trail testing for compliance

---

This task breakdown provides concrete, implementable steps for building the complete TrojanHorse intelligence system while maintaining privacy and performance standards.