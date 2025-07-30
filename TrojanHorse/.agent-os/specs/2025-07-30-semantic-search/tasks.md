# Spec Tasks

## Tasks

- [ ] 1. **Add `sentence-transformers` and `numpy` to dependencies**
  - [ ] 1.1 Add `sentence-transformers` and `numpy` to `setup.py` or `requirements.txt`.

- [ ] 2. **Update database schema**
  - [ ] 2.1 Add a column for vector embeddings to the transcriptions table in `search.py`.

- [ ] 3. **Implement `generate_embedding` function**
  - [ ] 3.1 Write tests for `generate_embedding`.
  - [ ] 3.2 Implement `generate_embedding` in `search.py`.
  - [ ] 3.3 Verify all tests pass.

- [ ] 4. **Implement `store_embedding` function**
  - [ ] 4.1 Write tests for `store_embedding`.
  - [ ] 4.2 Implement `store_embedding` in `search.py`.
  - [ ] 4.3 Modify `transcribe.py` to call `store_embedding` after each transcription.
  - [ ] 4.4 Verify all tests pass.

- [ ] 5. **Implement `semantic_search` function**
  - [ ] 5.1 Write tests for `semantic_search`.
  - [ ] 5.2 Implement `semantic_search` in `search.py`.
  - [ ] 5.3 Verify all tests pass.

- [ ] 6. **Enhance search interface**
  - [ ] 6.1 Add an option to the command-line interface for semantic search queries.
