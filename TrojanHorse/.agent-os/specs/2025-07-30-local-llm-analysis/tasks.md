# Spec Tasks

## Tasks

- [ ] 1. **Setup Ollama**
  - [ ] 1.1 Install Ollama on the local machine.
  - [ ] 1.2 Pull the selected LLM model.

- [ ] 2. **Create `analyze.py` module**
  - [ ] 2.1 Create the `analyze.py` file in the `TrojanHorse` directory.
  - [ ] 2.2 Add the `ollama` library to the project dependencies.

- [ ] 3. **Implement `summarize` function**
  - [ ] 3.1 Write tests for the `summarize` function.
  - [ ] 3.2 Implement the `summarize` function in `analyze.py`.
  - [ ] 3.3 Verify all tests pass.

- [ ] 4. **Implement `extract_action_items` function**
  - [ ] 4.1 Write tests for the `extract_action_items` function.
  - [ ] 4.2 Implement the `extract_action_items` function in `analyze.py`.
  - [ ] 4.3 Verify all tests pass.

- [ ] 5. **Integrate with daily notes**
  - [ ] 5.1 Modify the `transcribe.py` script to call the `analyze.py` module after transcription.
  - [ ] 5.2 Append the summary and action items to the daily notes file.
