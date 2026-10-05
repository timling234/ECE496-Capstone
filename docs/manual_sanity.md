# Offline manual sanity checks

Paste these PowerShell commands from the ECE496 repository root. They use the available bundled Python; substitute your own Python 3 executable if needed. No live API calls or credentials are used. Both demos create and remove an isolated temporary database, never `.tmp/store_poc.sqlite3`.

## Automated verification

COMMAND:

```powershell
& 'C:\Users\lingt\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests -p 'test_*.py' -v
```

EXPECTED: `Ran 24 tests` and `OK`. Covers normalization, storage/readback, default relevance, exact duplicate grouping, source/editorial preservation, idempotency and offline replay.

## FR-5 deterministic SQLite demo

COMMAND:

```powershell
& 'C:\Users\lingt\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m src.duplicate_demo
```

EXPECTED: A (X) and B (Bluesky) both contain `New paper published` and show the same `exact-v1:...` group ID. C contains `Different announcement` and shows `group=none`. All three show `candidate` and `publication=pending`. Summary: `posts=3; candidates=3; duplicate groups=1`. Final line confirms removal of the temporary database.

The demo closes and reopens SQLite and prints persisted rows with a join of `posts`, `relevance`, and `duplicate_candidates`. This CLI output is the manual database inspection, not just an in-memory matching result. No representative is selected.

## Offline replay demo

COMMAND:

```powershell
& 'C:\Users\lingt\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m src.duplicate_demo --reprocess
```

EXPECTED: `review candidates: 3; duplicate candidate groups: 1` followed by `Source rows and publication decisions unchanged; no API calls.` The reopened SQLite rows still show A+B in one group, C ungrouped, and all publication states pending. Temporary database removed afterward.

## Inspect the real Store without writing

COMMAND:

```powershell
& 'C:\Users\lingt\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' src/store_poc.py --inspect
```

EXPECTED: `stored post counts: {'bluesky': 3, 'x': 3}` for the original six-post POC database. Counts may change after additional imports. A missing database yields a clear failure and is not created. This command is read-only and does not add duplicate groups.

To intentionally replay derived stages on a chosen existing database later, use `src/store_poc.py --reprocess --db <path>`. Replay changes derived relevance/duplicate tables using MVP defaults; it leaves source rows and publication decisions untouched. Use the isolated demo above for the first sanity check.
