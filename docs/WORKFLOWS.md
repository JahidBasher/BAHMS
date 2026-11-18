# Working with BAHMS in Claude Code and Codex

BAHMS works underneath your existing VS Code workflow. You converse normally with Claude Code or Codex; the assistants use `.bahms/memory.py` as a shared CLI. There is **no dedicated chat UI** and **no MCP requirement** in the current build.

> **Agent instructions are best effort.** In important sessions, verify that a checkpoint or experiment note was saved before switching models. Do not rely on the agent's claim alone.

## 1. First session in an existing project

1. Open **your research project** in VS Code, not the BAHMS installer repository.
2. Verify: `python3 .bahms/memory.py status`.
3. Open Claude Code and send:

> Read `AGENTS.md` and review the existing project's README, methodology, and relevant implementation files. Call BAHMS `status` and retrieve bounded context. Identify the project's goal, constraints, architectures, known experiments, current uncertainties, and next actionable tasks. Save only evidence-backed **draft** notes referencing actual project files. Do not invent results or recursively read the whole project. Checkpoint R0 and summarize what you stored.

4. Inspect the results:

```bash
python3 .bahms/memory.py status
python3 .bahms/memory.py search 'research objective'
python3 .bahms/memory.py export
```

Generated `export/` Markdown is read-only. Correct records via the memory engine, not by editing these views. Existing code and data remain in their original locations.

## 2. Branch into an alternative hypothesis

A **BAHMS research branch** represents a conceptual research path, not a Git branch. You can ask Claude to create one, or use the commands below:

```bash
python3 .bahms/memory.py branch H1 'Learned binary hashing' --parent R0
python3 .bahms/memory.py switch H1
python3 .bahms/memory.py context --branch H1 \
  --task 'Compare learned hashing with HNSW and IVF-PQ' --budget 1400
```

Tell Claude:

> Work on research branch H1. Review its parent assumptions, relevant baselines, and prior failure evidence. Build an experiment plan and store the hypothesis as draft with source references. Do not mark planned experiments as completed.

Store actual results with artifact paths:

```bash
python3 .bahms/memory.py remember --branch H1 --kind experiment \
  --title 'ANN baseline, run 01' \
  --summary 'Run completed. See metrics and environment file; results require review.' \
  --source 'experiments/run01/metrics.json'
python3 .bahms/memory.py checkpoint --branch H1 \
  --summary 'Implemented baseline; inspect run01 metrics; next compare recall at equal memory budget.'
```

BAHMS stores **the summary and reference**, not a copy of the dataset or model weights.

## 3. Pause H1, try H2, revisit H1

```bash
python3 .bahms/memory.py branch H2 'Adaptive hash length' --parent R0
python3 .bahms/memory.py switch H2
python3 .bahms/memory.py context --branch H2 \
  --task 'Explore adaptive bit allocation' --budget 1400
```

You can now ask Claude to work on H2 while H1's checkpoint remains in the database.

Weeks later:

```bash
python3 .bahms/memory.py switch H1
python3 .bahms/memory.py context --branch H1 \
  --task 'Revisit H1 using the new adaptive-bit findings from H2' --budget 1400
```

The memory engine prioritizes H1 and ancestor context, but can retrieve matching H2 records via lexical search or graph links. It **does not automatically determine** whether H2's new evidence overturns H1: ask the agent to check applicability and original sources.

## 4. Hand off from Claude to Codex

In Claude Code:

> Before stopping, persist the verified work, list the exact artifacts, open questions, and next task, then checkpoint H1 in BAHMS. Report the checkpoint ID and whether any claims require review.

Close that conversation. In Codex, open the **same project folder** and say:

> Read `AGENTS.md` and use BAHMS `status` and `context` for H1. Continue from the latest checkpoint rather than relying on Claude's chat history. Verify the referenced evidence, implement the next small task, run tests, save verified results, and checkpoint again.

Verify cross-agent memory manually if necessary:

```bash
python3 .bahms/memory.py status
python3 .bahms/memory.py search 'ANN baseline'
python3 .bahms/memory.py cache-stats
```

## 5. Link evidence so knowledge can be reused

Create two records, then link the IDs from the `remember` output. Relations are directional:

```bash
# Example only: replace IDs with actual returned record IDs
python3 .bahms/memory.py link EXP-EXAMPLE CLAIM-EXAMPLE supports
```

For `supports`, the edge is **evidence -> supported claim**. For `depends_on` and `derived_from`, the edge is **dependent -> upstream source**. If you later modify a source record using the Python backend's versioned update API, affected descendants can be marked `needs_review` and their cached summaries invalidated. The CLI in the current release can create and link records but **cannot directly update existing records**.

## 6. When to checkpoint

Checkpoint after a completed milestone, a verified experiment, a substantial architectural decision, and **before switching agents or research paths**. A good checkpoint includes:

- Branch and current research objective
- Completed work versus untested proposals
- Evidence and artifact locations
- Failed experiments and reproducibility details
- Remaining blockers, next executable step

Do not checkpoint after every message. The purpose is to preserve durable progress, not every conversational token.

## 7. What is saved and what is not

| Saved to BAHMS | Not saved automatically |
| --- | --- |
| Hypothesis/experiment/decision summary records | Every LLM message, thought, or tool call |
| Research branch ancestry and checkpoint links | A fully runnable experiment environment |
| Paths/URIs identifying source evidence | Copies of arbitrary referenced files |
| Event metadata and JSON checkpoint snapshot | Memory synchronization across devices |
| Compact L2/L3 summaries | Trained embedding or predictive cache models |

The local memory DB is ignored by Git; source project commits do not automatically back it up. Securely back up `.bahms/data/` or the private checkpoint snapshot plus source artifacts. If two assistants operate simultaneously, use explicit `--branch` arguments and separate Git worktrees for conflicting code changes. Do not assume this MVP handles distributed write coordination.

## 8. Common troubleshooting

- **`BAHMS not initialized`:** Run `python3 .bahms/memory.py init` from the target project root.
- **`No relevant memory`:** Check `status`, then `search` with specific terms. Ensure important findings were saved and use explicit source references. FTS5 is lexical, so synonyms can be missed.
- **Agent isn't saving work:** Explicitly request a `remember` and `checkpoint`, then verify with `status` and `search`.
- **Claude and Codex disagree on active branch:** Run `status` and set `switch H1` for sequential work, or supply `--branch H1` in concurrent tasks.
- **Portable snapshot missing:** Run `checkpoint` or `snapshot` and back up `.bahms/shared/memory.json` securely.
- **Source facts contradict:** Check the original experiment artifacts; update the authoritative record through the Python API and review affected dependent records.

See [Command reference](COMMAND_REFERENCE.md), [Architecture](ARCHITECTURE.md), and [Installation](../INSTALLATION.md).
