---
name: changelog
description: Maintain CHANGELOG.md as a concise record of user-visible integration, action, config-flow, and security behavior. Use when adding release notes, documenting shipped user-facing features, or editing the [Unreleased] section.
---

# Changelog

Follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the policy in [CONTRIBUTING.md](../../../CONTRIBUTING.md#changelog-policy). Prefer the condensed style of the current [CHANGELOG.md](../../../CHANGELOG.md): short outcome bullets grouped by setup, actions, and security—not protocol or attribute dumps.

## Include

Add an entry when users can observe a new or changed:

- config flow step, option, or abort reason;
- action (service), action field, or response field;
- setup/unload/reload behavior that affects the UI or automations;
- security property (permission checks).

Write outcomes, not implementation history:

```markdown
- Config flow rejects a second Calendar Actions entry.
```

Do not name internal Home Assistant APIs or helper functions.

## Exclude

Do not mention scaffolding of repository packages, internal refactors, test harnesses, CI/lint changes, agent rules/skills, or documentation-only work.

Keep related details under one feature bullet.

## Sections

Use `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, and `Security`.

Before a published baseline, put shipped behavior under `Added` only. Do not use `Fixed`, `Changed`, or `Removed` until users could obtain the prior behavior from a tagged release.

If a change has no user-visible behavior, leave the changelog untouched.
