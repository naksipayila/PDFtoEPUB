# AGENTS.md

This file contains the project's permanent working rules and the core context required by the AI agent.
Keep information that changes between sessions in `PROGRESS.md` and `TODO.md` instead of adding it to this file.

## Context Files

- Product purpose and user context: `docs/product-context.md`
- Technical structure, commands, and tools: `docs/tech-context.md`
- System architecture and component relationships: `docs/architecture.md`
- Code, testing, and Git rules: `docs/conventions.md`

Use these files as the context map. Read `PROGRESS.md` and `TODO.md` at the start of a session, and read other task-relevant files before making changes.
OpenCode loads this file automatically; referenced files are not loaded automatically.

## Coding Rules

- Follow existing project patterns before introducing a new abstraction.
- Make the smallest correct change; do not add unrelated refactors.
- Preserve type safety and follow the existing lint/format rules.
- Handle error conditions explicitly; do not silently swallow errors.
- Do not add sensitive information, tokens, or secrets to source code or logs.
- When adding new behavior, add an appropriate test or explain why a test cannot be added.
- Do not change dependencies, APIs, or data formats unless the user requests it.

Read `docs/conventions.md` for detailed rules.

## Working Protocol

1. Inspect relevant files, tests, and existing usage points before making changes.
2. Do not hide uncertainty behind assumptions; ask the user when the impact is significant.
3. After making changes, run appropriate format, lint, test, and build commands.
4. Clearly report the results and any testing gaps.
5. Do not run destructive Git or file operations without the user's approval.

## OpenCode Tool and Security Rules

These rules are the permanent reference for agent behavior. `opencode.json` is used only for technical tool permissions; product and working instructions must not be split between two sources.

- Do not read or modify `.env`, `.env.*`, or similar secret files. Only `.env.example` may be read.
- Get explicit user approval before running Bash commands. Read-only `git status`, `git diff`, `git log`, and `git show` commands are exceptions that do not require approval.
- Do not run `git reset`, `git restore`, `git checkout --`, `git clean`, `rm`, `Remove-Item`, `del`, or `rmdir` without the user's explicit approval.
- Do not commit or push unless the user explicitly requests it.
- Do not modify or undo existing user changes without inspecting them first.

## Session Protocol

Read these files at the start of every session:

- `PROGRESS.md`
- `TODO.md`
- The `docs/` files relevant to the task
- Decisions in `docs/decisions/` that affect the task

At the end of every session:

- Update `PROGRESS.md` with completed work, validations, and next steps.
- Update `TODO.md` with completed or new tasks.
- Create an ADR under `docs/decisions/` if a permanent architectural or technical decision was made.
- Do not delete historical records unless the user requests it; add the new state as a new record.

## Change Boundaries

- Files that must not be modified: `.env`, `.env.*` except `.env.example`, committed user input PDFs, and unrelated user-owned worktree files. Generated `.venv`, `.runtime`, cache, log, and output files must not be committed as source changes.
- APIs that must be preserved: The `python run.py` GUI/CLI entry point, the installed `pdf-to-epub` CLI entry point, `python -m app`, and the public `PdfToEpubConverter.convert()` service used by both interfaces. The EPUB 3 package contract must remain valid.
- Operations carrying a data-loss risk: Publishing to an existing EPUB path replaces that file; the Windows bootstrapper refreshes the local runtime under `%LOCALAPPDATA%\PDFtoEPUB` and cleans temporary staging data. Input PDFs must remain read-only.
- Commit/push authorization: User approval is required.

## Source of Truth

When sources conflict, use this priority order:

1. The user's explicit instruction in the current session
2. Verifiable behavior from the working code and tests
3. Permanent rules in this file
4. Documentation under `docs/`
5. Assumptions

When a decision or rule changes, update the relevant documentation in the same change.
