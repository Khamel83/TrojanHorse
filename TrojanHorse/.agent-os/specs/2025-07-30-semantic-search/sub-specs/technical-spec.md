# Technical Specification

This is the technical specification for the spec detailed in @.agent-os/specs/2025-07-30-semantic-search/spec.md

## Technical Requirements

- The `search.py` module will be extended to include functions for:
  - `generate_embedding(text: str) -> list[float]`: Generates a vector embedding for a given text using a pre-trained model (e.g., Sentence Transformers).
  - `store_embedding(transcription_id: int, embedding: list[float])`: Stores the embedding in the SQLite database, linked to the transcription.
  - `semantic_search(query_embedding: list[float], top_k: int) -> list[dict]`: Performs a similarity search using cosine similarity to find the top_k most similar transcriptions.
- The SQLite database schema will be updated to include a column for storing vector embeddings.

## External Dependencies

- **sentence-transformers:** Python library for generating sentence embeddings.
  - **Justification:** Provides pre-trained models for generating high-quality vector embeddings.
- **numpy:** Python library for numerical operations.
  - **Justification:** Required for vector operations (e.g., cosine similarity).
