# BAHMS — Branch-Aware Hierarchical Memory System

A lightweight, local-first research-memory add-on for **Claude Code** and **Codex** in VS Code.

**Status:** experimental prototype (stdlib Python, SQLite FTS5). It provides persistent hypothesis branches, source-linked notes, task-scoped retrieval, checkpoints, an append-only event history, and simple L2/L3 caches. It does **not** yet implement learned predictive caching, automatic complete capture of every agent action, embedding retrieval, or distributed multi-user synchronization.

## Install into an existing project

Requires **Python 3.10+** with SQLite FTS5.

```bash
# Clone this BAHMS tool once
git clone https://github.com/YOUR_USERNAME/bahms.git ~/Tools/bahms

# Install memory into an existing VS Code project
cd /path/to/existing/research-project
python3 ~/Tools/bahms/install_bahms.py .
python3 .bahms/memory.py status
```

For a **new project**, create its directory first, then run the same command. To install into multiple projects:

```bash
python3 ~/Tools/bahms/install_bahms.py ~/Research/ProjectA ~/Research/ProjectB
```

### Use with Claude Code or Codex

Open the **target project folder** in VS Code. The installer appends shared memory instructions to `AGENTS.md` and adds an `@AGENTS.md` import to `CLAUDE.md` when needed. Existing contents are preserved.

Suggested first agent message:

> Read AGENTS.md and the project's relevant README/docs. Initialize an evidence-backed BAHMS research baseline as draft memories, checkpoint the active branch, and explain what was saved. Do not invent experiments or load the entire repository.

In later sessions, both assistants can retrieve bounded context and update the same on-disk memory if they operate in the same local folder. Use sequential sessions initially; parallel agents require explicit branch IDs and coordinated writes.

## Common commands (run in the **target** project)

```bash
python3 .bahms/memory.py status
python3 .bahms/memory.py branch H1 'Alternative hypothesis' --parent R0
python3 .bahms/memory.py switch H1
python3 .bahms/memory.py context --branch H1 --task 'Next experiment' --budget 1400
python3 .bahms/memory.py checkpoint --branch H1 --summary 'Validated work, references, blockers, next steps'
python3 .bahms/memory.py export
python3 .bahms/memory.py doctor
```

## Architecture

- **L1:** task-relevant prompt text selected within an approximate token budget.
- **L2:** small cache scoped to the currently active hypothesis branch.
- **L3:** cross-branch project cache.
- **L4:** SQLite authoritative graph, events, records and referenced artifacts.
- **Research branches are not Git branches.** Claude and Codex share the same memory backend and instructions, not their original chat transcripts.

For API and install details, see [Installation](INSTALLATION.md) and [removal instructions](UNINSTALL.md).

## Privacy, backups and limitations

- `.bahms/data/` contains the **private local SQLite database** and is ignored by Git.
- `.bahms/shared/` contains **private portable snapshots** and is also ignored by Git. Back up securely outside Git if you need to move memory between machines.
- `.bahms/export/` is a generated readable view and is ignored by Git.
- **Never commit** credentials, private research notes, raw datasets, model weights, or experiment artifacts without deliberate review.
- Snapshot files are not automatically synchronized to GitHub. Versioning the BAHMS source code is separate from backing up a research project's memory.
- You must verify critical scientific conclusions against source artifacts. Retrieval may be incomplete, and agents may not follow every instruction reliably.

## Run tests

```bash
python3 -m unittest discover -s tests -v
```

No external Python dependencies are required.

## License

No open-source license has been selected yet. Add a license before publishing for general reuse or accepting outside contributions.
