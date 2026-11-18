# BAHMS — Add-on for existing VS Code research projects

This installs **branch-aware persistent research memory** into an existing project folder, without moving your source code, replacing your project instructions, adding any pip dependencies, or configuring MCP.

## One-time installation (macOS / Linux)

1. Clone this repository (for example, `git clone https://github.com/JahidBasher/BAHMS.git ~/Tools/BAHMS`).
2. In VS Code, open your **existing** research project folder (not the extracted add-on folder).
3. Open **Terminal → New Terminal** and run:

```bash
python3 ~/Tools/BAHMS/install_bahms.py .
```

Replace the path if you extracted elsewhere. `.` means *the current existing project folder*. Python 3.10+ is required, with an SQLite build that has FTS5 (the normal CPython distribution does).

You can install into multiple projects from any directory:

```bash
python3 ~/Tools/BAHMS/install_bahms.py \
  ~/Research/project-one ~/Research/project-two
```

The installer modifies or creates only `AGENTS.md`, `CLAUDE.md`, `.gitignore`, and files under `.bahms/`. Existing code, papers, and reports are untouched. Existing instructions are appended to, not replaced. Run the installer again safely; it will not duplicate the appended instructions or silently overwrite different versions of its runtime scripts.

## One-time verification

From the project root:

```bash
python3 .bahms/memory.py status
python3 .bahms/memory.py context --task "Summarize the project's current research questions" --budget 1400
```

You should see the `R0` research branch and a `PROJECT-001` project-reference record. **BAHMS does not ingest and pretend to understand all your old research automatically.** Your first agent task should create a concise evidence-based baseline after selectively reading existing README/docs. No API key or MCP setup is necessary.

## First message to Claude Code in VS Code

> Read `AGENTS.md` and the existing project README/docs. Use BAHMS to establish a concise, evidence-backed research baseline for this existing repository. Record the active research directions and important confirmed decisions as draft records with source file references. Do not scan or embed the entire repo, invent experiments, or change source code. Checkpoint the branch and tell me what you saved.

## Later messages to Claude

> Continue our current research branch. Check BAHMS for the latest checkpoint, relevant experiments, and unresolved questions before working. Save your verified results and checkpoint when done.

## Switch to Codex

Open the Codex VS Code extension in **the same folder** and start a new chat:

> Continue the research from BAHMS's shared memory. Review Claude's latest checkpoint and evidence, implement the next planned task, run tests, and save new verified results with artifact references. Do not assume you can see Claude's chat history.

This verifies cross-agent handoff through the same SQLite database, not through conversation transfer.

## Creating and resuming research branches (usually done by the agents)

```bash
python3 .bahms/memory.py branch H1 "First alternative" --parent R0
python3 .bahms/memory.py switch H1
python3 .bahms/memory.py context --branch H1 --task "Continue first alternative" --budget 1400
python3 .bahms/memory.py remember --branch H1 --kind hypothesis --title "Hypothesis" --summary "Tentative, untested hypothesis" --source "docs/hypothesis.md"
python3 .bahms/memory.py checkpoint --branch H1 --summary "Evidence collected; next steps; remaining uncertainties"
```

You do *not* need these commands during routine work if the agent follows its project instructions. They are useful for troubleshooting or manual recovery.

## What persists, and where

```text
existing-project/
├── AGENTS.md                  # shared Claude + Codex project rules
├── CLAUDE.md                  # imports AGENTS.md (existing instructions preserved)
├── .bahms/
│   ├── memory.py              # commands for agents or humans
│   ├── core.py                # graph + cache + retrieval backend
│   ├── data/
│   │   ├── memory.sqlite      # authoritative LOCAL persistent state (gitignored)
│   │   └── active_branch.txt  # suggested branch; use --branch for concurrent agents
│   ├── shared/
│   │   └── memory.json        # portable backup created at checkpoint (ignored by Git)
│   └── export/               # generated human-readable Markdown (read-only)
└── [your existing project files]
```

- L1: bounded text selected into a model prompt.
- L2: SQLite branch cache.
- L3: SQLite project-wide cache.
- L4: persistent authoritative records, edges, event history and source artifacts.

A checkpoint automatically writes a portable JSON snapshot in `.bahms/shared/memory.json`; it is ignored by Git and should be backed up separately. If the DB is lost, you can restore this snapshot into a fresh local DB by keeping `.bahms/shared/memory.json` and running `python3 .bahms/memory.py init` after restoring/clearing the local DB. Keep backups: snapshots are NOT cloud sync, and do not include research data files unless those are separately backed up.

**Existing AGENTS/CLAUDE instructions and possible conflicts:** the add-on preserves them, but agents can still misunderstand or ignore instructions. For important tasks verify with `python3 .bahms/memory.py status` and `search`/`get`. A hook or MCP integration can later improve automatic enforcement.

**Concurrent agents:** start sequentially for now. Both agents see the same `active_branch.txt`. When running simultaneously, tell each to use explicit `--branch H1`, `--branch H2` (or distinct Git worktrees for code) and avoid uncontrolled shared edits.

**Model context size:** persistence can represent much more than a model's context window, but doesn't guarantee that every needed source will be retrieved. This prototype uses lexical FTS retrieval, rough token budgeting, and a simple cache policy. Learned predictive caching and vector retrieval are not included.

## Privacy and maintenance

- Database is local; no account link is required to run it.
- BAHMS neither uploads nor indexes your files without the agent choosing to read them.
- The snapshot file can contain sensitive research information. Don't commit it to a public repository without review.
- Use `python3 .bahms/memory.py doctor` to check local database integrity.
- Export readable records with `python3 .bahms/memory.py export`.
- Use `python3 .bahms/memory.py cache-stats` to view external cache statistics.
- `AGENTS.md` and `CLAUDE.md` must be available in the project root that both agents open.

## Scope

The add-on supports persistent research branches and lightweight bounded retrieval. It is not an autonomous research platform, a reliable one-million-token reasoning engine, or a production multi-user database. Existing project documents are preserved, not bulk-imported. Improvements beyond the MVP should be measured using task success and provenance correctness, not just cache hit rate.

## Further reading

- [Architecture and cache semantics](docs/ARCHITECTURE.md)
- [Claude Code ↔ Codex research workflows](docs/WORKFLOWS.md)
- [Full CLI reference](docs/COMMAND_REFERENCE.md)
