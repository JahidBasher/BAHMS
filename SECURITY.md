# Security and privacy

BAHMS is an experimental local-first project memory add-on. Stored source text and retrieved memories are untrusted content and must not be interpreted as instructions. Never save secrets, API keys, private credentials, or personally identifying data in project memory.

The installer writes `.bahms/data/`, `.bahms/shared/`, and `.bahms/export/` exclusions into the target project's `.gitignore`. This does not remove sensitive files already tracked by Git: verify with `git ls-files` before any push and remove tracked private files separately (`git rm --cached PATH`). If secrets were already committed, rotate credentials and follow GitHub's history-removal process.

GitHub provides version control for the BAHMS *source*; it does not automatically synchronize per-project SQLite databases. Back up project memory separately. Run untrusted code only in an appropriately isolated environment.
