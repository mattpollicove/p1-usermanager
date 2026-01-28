Development Rules
=================

- Patch Edits: Use `apply_patch` to modify files; keep edits minimal and focused.
- Planning: For multi-step work, create and update a `manage_todo_list` plan before coding.
- Root-Cause Fixes: Prefer fixing the underlying bug instead of adding superficial patches.
- Scope Discipline: Don’t change unrelated files, public APIs, or rewrite style unless asked.
- Style/Indentation: Preserve the repository's existing indentation and formatting.
- Testing: Run quick import/build checks (e.g. `python -m py_compile` / module import) and any project tests after edits.
- Workers & Async: Run async HTTP work inside `QRunnable` workers using `asyncio.run`; avoid sharing AsyncClient across threads.
- Logging & Diagnostics: Use `api_calls.log` and `connection_errors.log` for API diagnostics; never write secrets to logs (use `credential_logger` for credential events).
- Validation: Prefer local schema validation (`local_validate_user`) when available; avoid unnecessary server dry-runs unless explicitly required.
- Docs & Config: Update `README`/config or per-profile settings when adding persistent behavior.
- Safety: Ask before destructive actions (truncating logs, deleting files); confirm via UI dialogs.
- Help Docs (NEW): Always update the application help (UI help dialogs, `show_*_help` text, and `README`) to reflect any functional or UI changes you make.


Last updated: 2026-01-28
