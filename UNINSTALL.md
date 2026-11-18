# Undoing the add-on

BAHMS does not replace source code, project configuration or existing instructions. If needed:

1. **Back up** `.bahms/data/memory.sqlite` and `.bahms/shared/memory.json` before changing anything.
2. Remove only the `<!-- BAHMS:BEGIN ... -->` through `<!-- BAHMS:END ... -->` section from `AGENTS.md`.
3. Remove the `<!-- BAHMS shared instructions -->` and `@AGENTS.md` import that the installer appended to `CLAUDE.md` (only if your own instructions don't rely on that import).
4. Delete `.bahms/` if you want to discard the engine, all local memory and exports.
5. Optionally remove the `.bahms/data/` and `.bahms/export/` lines from `.gitignore`.

If `AGENTS.md` or `CLAUDE.md` originally existed, do not delete the whole file.
