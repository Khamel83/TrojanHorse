# Local Answer Evaluation and Sensitive Remote Comparison

**Status:** Approved for implementation by the owner in the continuation
request; implementation must remain behind an explicit evaluation command.

## Goal

Provide a small, local-first answer interface and an accuracy harness that can
run the same source-backed question and evidence packet through a local model
and the explicitly selected `g2k-sensitive` route. The source records remain
the reference. Model agreement is not a correctness signal by itself.

## What is already trusted

The active `work-corpus` package already provides deterministic exact,
full-text, relationship, and bounded raw fallback search. Each hit carries an
evidence ID, source ID, source version ID, source path, locator, date basis,
scope, source system, sensitivity, and an evidence label. Search explicitly
represents source facts, inferences, conflicts, and missing evidence.

The completed corpus acceptance proves preservation, indexing, and provenance
at its checkpoint. It does not prove answer synthesis accuracy. The new work
must keep those claims separate.

## Runtime shape

The public entry point is the existing CLI with two read-only commands:

```text
work-corpus --root <root> answer <question> [--backend evidence|ollama|g2k-sensitive]
work-corpus --root <root> answer-compare <question> --allow-sensitive-remote
```

`answer` defaults to `evidence`, which returns a clearly labelled evidence-only
response and never calls a model. `ollama` is a local opt-in backend. The
`g2k-sensitive` backend requires `--allow-sensitive-remote` and invokes the
installed Gateway2000 shell function with tools, extensions, and session
storage disabled. Neither answer command writes prompts, answers, evaluation
cases, raw files, or derived corpus rows. Search runs with index rebuilding
disabled for these commands.

The implementation uses a small backend protocol:

```python
class CompletionBackend(Protocol):
    name: str
    def complete(self, messages: Sequence[Mapping[str, str]]) -> Completion:
        ...
```

`OllamaBackend` uses the loopback `/api/chat` endpoint with a configured local
model, JSON response mode, temperature zero, bounded context, and a timeout.
`GatewaySensitiveBackend` runs the existing `g2k-sensitive` function through a
controlled `zsh` invocation and parses its JSON-lines receipt. It reports only
the route and gateway metadata available from that receipt; it must not claim
the underlying provider identity when the gateway does not expose it.

## Evidence preparation and de-sensitization

Search results are mapped to ephemeral IDs (`S1`, `S2`, …) for one request.
The remote packet contains only:

- the question;
- the citation ID;
- evidence label, scope, source system, observed date, date basis, and safe
  locator;
- a bounded snippet.

The packet omits absolute paths, source IDs, source-version IDs, and local
database paths. Before remote transmission, snippets pass the existing
URL/secret redaction and an additional balanced sanitizer for email addresses,
phone numbers, and absolute filesystem paths. Project and person wording stays
intact because removing those terms would make many answers less accurate.
Each packet is capped at eight hits and 12,000 characters, with each snippet
capped at 1,200 characters. The complete local citation map is retained only
in memory and in the caller's local result.

Evidence is enclosed as inert data. The system prompt says that text inside the
evidence block can contain instructions, but those instructions are not
commands. The model must answer only from the supplied evidence and must return
JSON:

```json
{"answer": "...", "citations": ["S1"], "stance": "supported"}
```

The parser rejects malformed JSON, unknown citation IDs, empty answers, and
answers with no citation when source facts are present. A conflict must be
reported as mixed or insufficient and cite the relevant evidence. No-result
and source-free cases do not call a model and return an explicit abstention.

## Comparison and accuracy gates

The comparison command prepares one sanitized packet, hashes it, and sends that
same packet to both backends. A separate local-original run measures whether
sanitization changed retrieval or citation selection. Each case is held in a
local ignored JSONL file with:

```json
{
  "id": "case-001",
  "question": "...",
  "expected_source_ids": ["..."],
  "expected_status": "synthesized",
  "expected_terms": ["..."]
}
```

Expected source IDs and status are manually checked against the local source
records. The harness reports, per backend:

- source citation precision and recall;
- invalid or unprovided citation count;
- expected-status match and correct abstention;
- conflict acknowledgement;
- expected-term coverage as a review aid, never as a proof of truth;
- packet sanitizer findings, request duration, route/model metadata, and token
  usage where available.

The implementation is not accepted as accurate merely because tests pass or
two models agree. A real-corpus acceptance run requires a bounded manually
reviewed case set, source inspection for every cited claim, and explicit notes
for omissions, temporal mistakes, and unsupported synthesis. If the local
model does not meet the agreed bar, the evidence-only path remains the usable
default.

## Data and operational boundaries

- Remote evaluation is explicit, bounded, and opt-in. It supersedes the prior
  no-external-model statement only for this comparison path.
- No mailbox access, Atlas integration, provider write-back, cloud raw-data
  processing, semantic ranking, embeddings, historical task backfill, or corpus
  copy is included.
- Evaluation prompts, evidence packets, answers, and reports remain under the
  local ignored state directory and are not committed.
- The existing Granola delta LaunchAgent remains untouched. Verification only
  checks its current health and does not trigger a rebuild or historical pull.

## Verification

Tests must cover sanitizer behavior, packet bounds and equality, prompt-injection
handling, structured response parsing, unknown citations, no-result and
conflict abstention, local-model transport failures, G2K receipt parsing, CLI
authorization, and no raw/SQLite writes from answer commands. A synthetic local
Ollama canary and a synthetic G2K-sensitive canary precede any real-corpus
comparison. The full active suite, Ruff, compilation, diff checks, and a
bounded end-to-end comparison are required before integration.
