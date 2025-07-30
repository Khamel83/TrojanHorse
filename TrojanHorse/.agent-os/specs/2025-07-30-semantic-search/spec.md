# Spec Requirements Document

> Spec: Semantic Search
> Created: 2025-07-30
> Status: Planning

## Overview

Implement semantic search capabilities using vector embeddings to allow users to find content based on conceptual similarity, rather than just keywords.

## User Stories

### Conceptual Search

As a user, I want to search for concepts or ideas within my transcribed conversations, even if I don't remember the exact keywords, so that I can find relevant discussions more easily.

## Spec Scope

1. **Vector Embedding Generation:** Integrate with a local or cloud-based embedding model to generate vector embeddings for transcribed text.
2. **Vector Database Storage:** Store vector embeddings in the SQLite database alongside the transcribed text.
3. **Similarity Search:** Implement a similarity search algorithm to find content based on the semantic similarity of their embeddings.
4. **Search Interface Enhancement:** Enhance the search interface to allow for semantic search queries.

## Out of Scope

- Training custom embedding models.
- Real-time embedding generation during transcription.

## Expected Deliverable

1. Modifications to the `search.py` module to include vector embedding generation and similarity search.
2. The ability to perform semantic searches from the command line.
3. All transcribed content will have associated vector embeddings in the SQLite database.
