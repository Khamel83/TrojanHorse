# Spec Tasks

## Tasks

- [x] 1. **Setup OpenRouter**
  - [x] 1.1 Get an OpenRouter API key.
  - [x] 1.2 Add the API key to the `config.json` file.

- [x] 2. **Create `cloud_analyze.py` module**
  - [x] 2.1 Create the `cloud_analyze.py` file in the `TrojanHorse` directory.
  - [x] 2.2 Add the `requests` library to the project dependencies.

- [x] 3. **Implement `analyze` function**
  - [x] 3.1 Write tests for the `analyze` function.
  - [x] 3.2 Implement the `analyze` function in `cloud_analyze.py`.
  - [x] 3.3 Verify all tests pass.

- [x] 4. **Integrate with daily notes**
  - [x] 4.1 Modify the `transcribe.py` script to allow the user to choose between local and cloud analysis.
  - [x] 4.2 If cloud analysis is chosen, call the `cloud_analyze.py` module.
  - [x] 4.3 Append the analysis to the daily notes file.
