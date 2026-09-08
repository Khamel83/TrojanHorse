# Legacy Atlas lane

The root `TrojanHorse/` package, `th` command, `bridge/` synchronizer, and
`systemd/` deployment notes are retained as historical material only.

They are not installed, imported, tested, scheduled, or connected to the local
work corpus. They are not part of the supported architecture. The supported
entry point is the `work-corpus/` package and its `work-corpus` command.

Do not run the old bridge against `data/`. It sends files to Atlas and conflicts
with the local-only boundary in `docs/adr/0001-local-work-corpus-boundary.md`.
