# CLAUDE.md

All project context and rules are in AGENTS.md, imported below, so every AI tool reads the same brief.

@AGENTS.md

## Claude-specific notes
- Before editing, ask which workstream the user owns (WS1 to WS6 or lead) if it is not obvious from the branch name (`ws3/...`).
- Run `make check` after changes and report the result.
- For long data downloads, run them in the background and tell the user how to check progress.
