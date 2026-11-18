# BAHMS CLI command reference

Run these commands from the **root of a project where BAHMS has been installed**, not from the BAHMS tool source directory:

```bash
python3 .bahms/memory.py --help
```

| Command | Purpose | Example |
| --- | --- | --- |
| `init` | Initialize root branch or restore a snapshot during empty initialization | `python3 .bahms/memory.py init` |
| `status` | List branches, count records, inspect DB health | `python3 .bahms/memory.py status` |
| `doctor` | Report basic configuration/SQLite integrity | `python3 .bahms/memory.py doctor` |
| `branch ID NAME --parent PARENT` | Add a research hypothesis branch | `python3 .bahms/memory.py branch H1 'Learned hashing' --parent R0` |
| `switch ID` | Set shared default branch for sequential sessions | `python3 .bahms/memory.py switch H1` |
| `context --task TEXT [--branch ID] [--budget N]` | Return estimated-budget L1 memory selection | `python3 .bahms/memory.py context --branch H1 --task 'next experiment' --budget 1400` |
| `note --title --summary [--source] [--branch]` | Store a draft source-linked note | See below |
| `remember --kind --title --summary ...` | Store a draft typed record | See below |
| `get RECORD_ID` | Retrieve full one-record metadata and body | `python3 .bahms/memory.py get HYPOTHESIS-ID` |
| `search QUERY [--limit N]` | Search record text with lexical FTS5 | `python3 .bahms/memory.py search 'baseline latency' --limit 10` |
| `link SOURCE TARGET RELATION` | Add typed graph edge | `python3 .bahms/memory.py link EXP-ID CLAIM-ID supports` |
| `checkpoint --summary TEXT [--branch ID]` | Save resumable checkpoint and private JSON snapshot | See below |
| `snapshot` | Write private portable snapshot without creating a checkpoint record | `python3 .bahms/memory.py snapshot` |
| `restore` | Restore snapshot into an **empty** database | `python3 .bahms/memory.py restore` |
| `export` | Build read-only Markdown views | `python3 .bahms/memory.py export` |
| `cache-stats` | Inspect L2/L3 staging and hit counts | `python3 .bahms/memory.py cache-stats` |

## Creating source-backed records

```bash
python3 .bahms/memory.py note --branch R0 \
  --title 'Dataset selection rationale' \
  --summary 'Selected dataset based on modality coverage; evaluation not started.' \
  --source 'docs/dataset_selection.md'

python3 .bahms/memory.py remember --branch H1 --kind hypothesis \
  --title 'Learned hashing reduces index memory' \
  --summary 'Untested hypothesis; compare recall, p95 latency, and total index bytes.' \
  --source 'research/hypotheses/H1.md'
```

The valid `--kind` choices are `project`, `constraint`, `hypothesis`, `experiment`, `claim`, `decision`, `finding`, `checkpoint`, and `note`. `remember` also accepts `--body-file PATH` (read fuller content from an existing file) and `--id ID` (set a stable ID yourself). Stored records created through this CLI are **draft**. Use output IDs when linking evidence, and ensure `--source` identifies a real file or URI.

## Linking evidence

```bash
python3 .bahms/memory.py link EXP-ID CLAIM-ID supports
python3 .bahms/memory.py link CLAIM-ID EXP-ID depends_on
python3 .bahms/memory.py link CLAIM-A CLAIM-B contradicts
```

Relations: `supports`, `derived_from`, `depends_on`, `contradicts`, `relates_to`, `supersedes`, `tests`. The causal invalidation logic recognizes particular edge **directions**; see [Architecture](ARCHITECTURE.md).

## Checkpoint and handoff

```bash
python3 .bahms/memory.py checkpoint --branch H1 \
  --summary 'Completed retrieval baseline; source experiments/run01/metrics.json; next validate H1.'

python3 .bahms/memory.py get CKPT-RETURNED-ID
```

`checkpoint` updates the branch's `checkpoint_id` and writes `.bahms/shared/memory.json`. This JSON includes private research records and is excluded from Git. `export` creates read-only Markdown in `.bahms/export/` for human inspection; editing those files does not update the database.

## Recovery and safe upgrades

- Back up `.bahms/data/` and `.bahms/shared/` securely **outside the public Git repository**.
- Restore only into an empty database. Do not casually delete an active database or overwrite a newer project snapshot. Test restoration in a disposable project copy first.
- The installer refuses to overwrite modified `.bahms/core.py` or `.bahms/memory.py` files. Upgrading requires a deliberate runtime migration/review, not blind rerunning.
- SQLite databases are not automatically synchronized between different laptops or remote agents. A snapshot is an explicit backup, not real-time sync.

## CLI limitations

The current CLI does not expose versioned `update_record()` or `prefetch()` operations available in the Python backend. It also does not implement multi-project search, vector retrieval, learned cache prediction, automatic code experimentation, or complete concurrent-agent coordination. Its token accounting is approximate.
