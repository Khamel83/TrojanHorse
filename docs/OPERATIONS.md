# Work-corpus operations

The supported runtime is the local `work-corpus` package. It reads raw files
under `data/` and writes rebuildable state under `work-corpus/corpus/` and
`work-corpus/state/`.

## Install

From a clean checkout:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,documents]"
```

The install exposes `work-corpus`. The root `python -m pytest` command is
configured to run the active suite in `work-corpus/tests`; it does not collect
the quarantined root legacy tests.

## Safe checks

```bash
work-corpus --root . doctor
work-corpus --root . raw-verify
work-corpus --root . report
```

`doctor` does not make network calls or provider writes. `raw-verify` hashes the
raw tree twice and records whether any path, size, or byte hash changed between
the two reads. Neither command edits a raw source file.

## Ordered local refresh

```bash
work-corpus --root . inventory --full-hash
work-corpus --root . mcp-import
work-corpus --root . normalize
work-corpus --root . organize --run-date "$(date -u +%F)" --first-pass
work-corpus --root . views
work-corpus --root . report
```

Run the commands in this order. The raw source and provider captures remain in
place. The current active database is `work-corpus/state/work_corpus.sqlite`.

## Legacy boundary

The old Atlas bridge is quarantined. See [LEGACY_ATLAS.md](LEGACY_ATLAS.md).
Do not enable its launch agent or service files.

## Granola scheduler

The checked-in timer template is
`work-corpus/ops/systemd/work-corpus-granola-delta.timer`. It polls the
documented REST `updated_after` filter every five minutes, which is a freshness
choice rather than a provider requirement. The service obtains
`GRANOLA_API_KEY` through the local `secrets` broker and never places the key in
a command argument or repository file.

The first delta run seeds its watermark from the newest local REST archive. It
does not silently perform another historical full pull. Later runs use the
latest successful provider `updated_at` minus the configured overlap, preserve
the raw response, rerun the local stages, and advance the checkpoint only after
success. A failed local stage leaves the capture for diagnosis and keeps the
previous watermark.

Before enabling the timer:

1. Choose the host and checkout path.
2. Replace `/path/to/TrojanHorse` in both systemd unit references.
3. Confirm the host has the active Python environment and the `secrets`
   command can read `GRANOLA_API_KEY`.
4. Install the service and timer, then run one supervised service invocation.
5. Enable the timer and verify its journal plus
   `work-corpus/state/mcp/granola_rest_delta.json`.

The repository does not assume a production host because `homelab.yaml`
currently leaves that value unknown.
