# Spec Tasks

## Tasks

- [ ] 1. **Setup OpenRouter**
  - [ ] 1.1 Get an OpenRouter API key.
  - [ ] 1.2 Add the API key to the `config.json` file.

- [ ] 2. **Create `cloud_analyze.py` module**
  - [ ] 2.1 Create the `cloud_analyze.py` file in the `TrojanHorse` directory.
  - [ ] 2.2 Add the `requests` library to the project dependencies.

- [ ] 3. **Implement `analyze` function**
  - [ ] 3.1 Write tests for the `analyze` function.
  - [ ] 3.2 Implement the `analyze` function in `cloud_analyze.py`.
  - [ ] 3.3 Verify all tests pass.

- [ ] 4. **Integrate with daily notes**
  - [ ] 4.1 Modify the `transcribe.py` script to allow the user to choose between local and cloud analysis.
  - [ ] 4.2 If cloud analysis is chosen, call the `cloud_analyze.py` module.
  - [ ] 4.3 Append the analysis to the daily notes file.
