# Domain docs

This repo uses a **single-context** layout:

- `CONTEXT.md` — one file at the repo root describing the project's domain language, architecture, and key concepts.
- `docs/adr/` — architectural decision records live here as individual markdown files.

Skills that need domain context (`improve-codebase-architecture`, `diagnose`, `tdd`) read `CONTEXT.md` for terminology and `docs/adr/` for past decisions. Both paths are resolved relative to the repo root.
