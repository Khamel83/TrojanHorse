---
name: tdd
description: Test-driven development with mandatory RED-GREEN-REFACTOR cycle. Enforces writing failing tests before production code. Use when implementing new features, fixing bugs with test coverage, or when the user wants TDD discipline. Trigger keywords: tdd, test first, test driven, red green refactor, add tests, coverage, write a test, failing test.
---

# /tdd — Test-Driven Development

RED-GREEN-REFACTOR cycle. No production code without a failing test shown first.

## Usage

```
/tdd
/tdd <feature or behavior to implement>
```

## Behavior

### The Cycle

Repeat until the feature is complete:

#### RED: Write a Failing Test

1. **Understand what you're building** — read relevant files, check existing tests
2. **Write one test** that describes the desired behavior. The test must:
   - Be specific to one behavior
   - Fail for the right reason (not a syntax error or import issue)
   - Have a clear, descriptive name
3. **Run the test. Show the output.** It must fail. If it passes, something is wrong —
   either the feature already exists or the test is broken.
4. **Do not write any production code yet.** Only the test.

#### GREEN: Make It Pass

1. **Write the minimal code** to make the failing test pass.
2. **Run the test. Show the output.** It must pass.
3. **Don't over-engineer.** Write only what's needed to pass this one test.
4. **If you need to change the test to make it pass**, you've done it wrong —
   go back to RED.

#### REFACTOR: Clean Up

1. **Run all tests.** They must all still pass before refactoring.
2. **Clean up** — rename, extract, simplify. One change at a time.
3. **Run all tests after each refactoring step.** If anything breaks, revert.
4. **Stop refactoring** when the code is clean enough. Don't chase perfection.

### Rules

1. **No production code without a failing test shown first.** This is non-negotiable.
2. **One test, one fix.** Don't write 5 tests then implement everything at once.
3. **Tests are the spec.** If the behavior isn't tested, it doesn't exist.
4. **Show output.** Every RED and GREEN step must show actual test output, not assertions.

### When to Break the Rules

- **Bug fixes without tests**: If the existing code has no test infrastructure, write the test as part of the fix. RED and GREEN may happen in the same step, but the test must still come first.
- **Exploratory coding**: If you're genuinely unsure what the API should look like, you may prototype (then throw it away and start TDD for real).

### Integration with /conduct

When invoked inside a `/conduct` build loop:
- The TDD cycle replaces the normal implement-then-verify flow
- Each task in the build loop follows RED-GREEN-REFACTOR
- Phase 3 verification still runs at the end (it will pass because tests drove the implementation)

### Done

When all acceptance criteria are met and all tests pass:

```
TDD Complete
├─ Tests written: N
├─ Tests passing: N
├─ Cycles: N (RED-GREEN-REFACTOR)
└─ Coverage: {files/functions covered}
```
