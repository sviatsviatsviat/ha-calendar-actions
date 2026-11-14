---
name: conventional-commits
description: Draft intentional conventional commits for Calendar Actions changes. Use when committing, summarizing changes for commit, or the user asks for commit message help.
---

# Conventional commits

Use:

```text
<type>(<optional-scope>): <imperative subject>

<optional body explaining why>
```

Supported types:

| Type | Use |
|---|---|
| `feat` | New user-visible integration or action behavior |
| `fix` | Correction to user-visible or internal behavior |
| `refactor` | Code change without behavior change |
| `test` | Tests only |
| `docs` | Documentation only |
| `chore` | Build, CI, tooling, or dependency maintenance |

Useful scopes include `calendar_actions`, `services`, `config_flow`, `devcontainer`, and `tests`.

Use imperative mood, omit the trailing period, and keep the subject concise. Use the body for motivation, compatibility, or a non-obvious tradeoff.

Examples:

```text
feat(services): add THISANDFUTURE support to delete_event
fix(services): keep event duration when only dtstart changes
docs: explain config/custom_components symlink
chore(devcontainer): pin ffmpeg system package install
```
