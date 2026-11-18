# BAHMS architecture and implementation details

This document describes the **current MVP**, not a future proposed fully autonomous or learned memory system. See the [README](../README.md) for the quick start and [workflows](WORKFLOWS.md) for practical examples.

## Storage and consistency model

BAHMS makes **SQLite records and events authoritative**. The branch-local cache (L2), shared cache (L3), exported Markdown, and selected model context (L1) are derived representations. Full project source files and experimental artifacts remain in their ordinary project locations, referenced by `source_uri` on memory records.

| Layer | Actual MVP representation | Role |
| --- | --- | --- |
| L1 | Returned text from `context` | Bounded subset injected into a model prompt by the agent |
| L2 | SQLite `cache` rows scoped to research branch | Summaries of records from the active branch or its ancestry |
| L3 | SQLite `cache` rows scoped to `global` | Summaries of records retrieved from outside the active branch ancestry |
| L4 | SQLite `records`, `branches`, `edges`, `events` and referenced artifacts | Durable history and evidence source |

An L2/L3 entry is **not** the model's Transformer KV cache. It is a project-level semantic-summary cache. External staging does not itself use LLM context tokens.

## Data model

- `branches`: `id`, `name`, `parent_id`, status, latest `checkpoint_id`.
- `records`: `id`, `kind`, `branch_id`, `title`, `summary`, `body`, `status`, `review_state`, integer `version`, `pinned`, `source_uri`, timestamps.
- `edges`: typed relationships between record IDs: `supports`, `depends_on`, `derived_from`, `contradicts`, `relates_to`, `supersedes`, and `tests`.
- `events`: append-only operation **metadata** (created/updated/linked/checkpointed, etc.). It is not a full immutable snapshot of every previous document body or experimental file.
- `records_fts`: SQLite FTS5 index of title, summary, and body.
- `cache`: L2/L3 copies of record summaries with source version, estimated token cost, hits, and last access.

Record kinds: `project`, `constraint`, `hypothesis`, `experiment`, `claim`, `decision`, `finding`, `checkpoint`, `note`.

**Important:** `status=draft` means proposed or not approved. `review_state=needs_review` flags invalidated dependencies; neither field is a scientific truth guarantee. An agent's saved text must be checked against source artifacts for consequential decisions.

## Context selection: current algorithm

For `context --branch H1 --task "..." --budget 1400`, the engine:

1. Follows H1's parent pointers back to the R0 root.
2. Considers up to 128 globally pinned records.
3. Considers the branch and ancestor checkpoints plus up to 48 recent records **per branch**.
4. Adds up to 30 ranked FTS5 keyword matches for the task (including cross-branch results).
5. Optionally expands one hop along graph edges from a bounded candidate set.
6. Prioritizes active-branch and parent records, pinned constraints, checkpoints, and search relevance; gives `needs_review` records a lower ranking.
7. Selects compact summaries until the estimated `token_budget` and max-items limits are reached. It can fail if a pinned record cannot fit.
8. Reads/writes cached representations by record version. L2 contains branch/ancestor items; cross-branch items use L3.

Only the selected summaries and references are printed for the agent. To inspect detailed evidence, use `search`, `get`, and the actual source files. The token estimator currently approximates one token as four UTF-8 bytes, and is **not accurate for every language/model**. The current similarity search is **lexical FTS5, not embedding similarity**. It can miss relevant records with different terminology.

## Cache admission, replacement, and invalidation

The MVP stages a summary when a candidate is selected for context (or when the programmatic `prefetch()` method is called). External cache entries are scoped by tier and branch/global key. On a valid cache hit the stored summary is reused and hit count/access time updated. If the authoritative record version changed, it is discarded and rebuilt.

L2 and L3 each have configurable **estimated-token budgets** at the Python `MemoryStore` level (defaults: 8,000 for an L2 scope and 40,000 for the L3 scope). When capacity is exceeded, entries with the fewest hits and oldest access are evicted. This is a simple frequency/recency heuristic, **not a predictive or learning-based policy**.

The Python backend has `update_record(record_id, expected_version, ...)`. When a record changes, it increments the version, updates the FTS index, deletes affected cached representations, and recursively flags dependent records `needs_review` using supported graph-edge directions. Agents must verify those flags before continuing. **The current CLI does not expose a record-update command**; updates require the Python API or future tooling. Graph corrections are a best-effort dependency mechanism, not complete proof-level scientific consistency.

## Branches and recovery

A research branch has a parent hypothesis/trajectory. Child records can inherit context from ancestor branches without copying their documents. Switching the shared default with `switch` updates `.bahms/data/active_branch.txt`; it does not modify the Git branch, change the code workspace, or reload the model automatically.

`checkpoint` creates a branch-linked checkpoint record and writes `.bahms/shared/memory.json` containing branches, records, edges, and event history. External caches are deliberately **not** included and rebuild on retrieval. Original referenced files are also **not** part of this JSON snapshot and must be backed up separately.

A restore is accepted only into an **empty** database and should be tested on a separate copy before use. It does not merge snapshots from competing laptops or automatically reconcile concurrent research histories. This is local recovery, not continuous cloud synchronization.

## Practical limitations and next research steps

- No model or experiment runs automatically; LLM agents invoke the CLI under project instructions.
- No guarantee that an agent will record every important result; use checkpoints and verify status.
- No vector database, query-conditioned learned admission, branch-aware predictive prefetch, or multi-resolution representations yet.
- No distributed transaction service or conflict-free merging for simultaneous agent teams.
- No claim that large persistent storage improves reasoning without high-quality selective retrieval.

Suggested development order: (1) retrieval benchmark with exact-source grounding, (2) robust versioned snapshot history, (3) multi-resolution summaries and embeddings, (4) branch-locality-aware admission/prefetch, (5) concurrency and tested coherence, (6) human review UI. Keep each change measurable against the existing lexical/heuristic baseline.
