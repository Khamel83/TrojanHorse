---
name: debug
description: Systematic debugging with 4 mandatory phases. Use when fixing bugs, investigating errors, or troubleshooting unexpected behavior. DO NOT skip to the fix — investigate first. Trigger keywords: bug, error, broken, not working, crash, failing, debug, investigate, troubleshoot, wrong output, unexpected behavior, regression.
---

# /debug — Systematic Debugging Protocol

4-phase debugging. Phases 1-3 are read-only. No code changes until Phase 4.

## Usage

```
/debug
/debug <description of the problem>
```

## Behavior

### Phase 1: Investigate (READ-ONLY)

**Do not fix anything. Do not suggest fixes. Only observe.**

1. **Reproduce the bug** — get the exact error message, stack trace, or unexpected behavior.
   Show the actual error output. If you can't reproduce it, say so.
2. **Identify the symptom** — what's the expected behavior vs actual behavior?
3. **Gather context** — read relevant files. Look at:
   - The file/line where the error originates
   - Recent changes: `git log --oneline -10`
   - Related tests (do they pass or fail?)
   - Any configuration that affects this behavior
4. **Check for known causes** — common patterns:
   - Off-by-one errors
   - Null/undefined values not handled
   - Race conditions / timing issues
   - Wrong environment variable or missing config
   - Dependency version mismatch
   - State mutation side effects

**Output**: Write a structured summary to `1shot/DEBUG.md`:
```markdown
## Symptom
{what's wrong}

## Expected vs Actual
- Expected: {what should happen}
- Actual: {what happens instead}

## Error Output
```
{exact error, stack trace, or observation}
```

## Context
- Files read: {list}
- Recent changes: {relevant git log}
- Tests: {passing/failing}
```

### Phase 2: Analyze (READ-ONLY)

**Still no code changes. Identify the root cause class.**

1. **State the root cause hypothesis** — what's the most likely explanation?
2. **Classify the bug** — which pattern does it match?
   - Logic error (wrong condition, wrong comparison)
   - State bug (stale data, mutation side effect)
   - Integration issue (wrong API, missing dependency)
   - Environment issue (config, permissions, timing)
   - Data issue (wrong format, missing field, encoding)
3. **Trace the data flow** — follow the relevant data from input to the point of failure.
4. **Confirm with evidence** — point to the specific line(s) where things go wrong.

**Output**: Append to `1shot/DEBUG.md`:
```markdown
## Root Cause
{one-sentence explanation}

## Bug Class
{category from above}

## Evidence
- {file}:{line} — {why this is the problem}
- {file}:{line} — {supporting evidence}
```

### Phase 3: Hypothesize (READ-ONLY)

**Design the minimal fix before writing it.**

1. **State the fix** — exactly what change will resolve the root cause?
2. **Predict the impact** — what else could this change affect? What could break?
3. **Design a verification** — what test or observation will confirm the fix works?
4. **If uncertain**: propose a minimal diagnostic change (e.g., add logging) to confirm the hypothesis before applying the real fix.

**Output**: Append to `1shot/DEBUG.md`:
```markdown
## Proposed Fix
{exact change}

## Risk Assessment
- Could break: {list}
- Safe because: {reasoning}

## Verification Plan
{how to confirm the fix works}
```

Ask the user: "Does this analysis look right? Should I proceed with the fix?"

### Phase 4: Fix

**Now you may write code.**

1. Implement the fix from Phase 3.
2. **Verify**: run the reproduction case from Phase 1. Show it passes.
3. **Check for regressions**: run existing tests. Show they still pass.
4. **Add regression test if applicable** — a test that would have caught this bug.
5. Commit with message: `fix: {what was wrong}`

**Output**: Append to `1shot/DEBUG.md`:
```markdown
## Fix Applied
- Changed: {file}:{line}
- Verification: {test output}
- Regression test: {added or N/A}
```

### Done

```
Debug Complete
├─ Root cause: {one-liner}
├─ Bug class: {category}
├─ Files changed: {count}
├─ Verification: {pass/fail}
└─ Regression test: {added/skipped}
```
