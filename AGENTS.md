# Repository instructions

`ha-calendar-actions` is a Home Assistant custom integration that adds calendar actions (`custom_components/calendar_actions`, domain `calendar_actions`). Development targets a disposable HA instance under `config/` inside the Dev Container.

Read these committed references before changing behavior:

- [README](README.md) for HACS install, configuration, and shipped actions.
- [Contributing](CONTRIBUTING.md) for Dev Container setup, run/test/lint, docs, changelog, commits, and CI.
- [Changelog](CHANGELOG.md) for user-visible release notes.
- [Design](docs/design.md) for settled constraints, per-call checks, and the Home Assistant internals in use.
- [manifest.json](custom_components/calendar_actions/manifest.json) for domain, config flow, `single_config_entry`, version, and IoT class.
- [AGENTS.md](AGENTS.md) (this file) for non-negotiable agent workflow.
- Agent skills under [`.claude/skills/`](.claude/skills/): `changelog`, `ci-pins`, `conventional-commits`, `python-tests`. Claude Code loads them automatically; other agents (Codex, Cline) should read the matching `SKILL.md` when the task fits its description.

## Package map

- `custom_components/calendar_actions/`: the integration.
  - `__init__.py`: registers services in `async_setup`; config entry setup/unload.
  - `config_flow.py`: single-step, single-instance config flow.
  - `services.py`: service schemas, per-call checks, create/list/update/delete handlers.
  - `services.yaml` + `translations/en.json`: selectors/examples and the names/descriptions Assist reads.
- `docs/design.md`: constraints, internal APIs used, startup-safety procedure.
- `tests/`: pytest suite using `pytest-homeassistant-custom-component` with a real Local Calendar.
- `config/`: disposable Home Assistant config used by the debugger/tasks. `config/custom_components` is a symlink to `../custom_components` (created by the Dev Container post-create command).
- `.devcontainer/`: Python 3.14 Dev Container; venv at `/home/vscode/.venv`. Do not create a project-root `.venv` for day-to-day work unless asked.
- `.vscode/`: launch, tasks, and interpreter settings for that venv.
- `requirements-dev.txt`: pinned Home Assistant, `ical` (Local Calendar's requirement), pytest helper, ruff, debugpy.
- `pyproject.toml`: pytest and ruff configuration.
- `hacs.json`: HACS metadata.

## Non-negotiable boundaries

- Integration code lives only under `custom_components/calendar_actions/`. Do not copy it into `config/`; rely on the symlink.
- Do not modify a production Home Assistant install; use `config/` only.
- Call calendar entities in-process like the calendar WebSocket handlers. No HTTP, tokens, `shell_command` or `python_script`.
- No lazy imports and no `try`-wrapped imports; Home Assistant already isolates import failures (see [docs/design.md](docs/design.md#startup-safety)).
- Keep every per-call check from [docs/design.md](docs/design.md#per-call-checks) on every service.
- Pin dependency versions in `requirements-dev.txt`. When bumping one pin, update every reference to that dependency in the same change. Keep pins synchronized with CONTRIBUTING/AGENTS verification commands; audit workflow `uses:` pins with [`.claude/skills/ci-pins/SKILL.md`](.claude/skills/ci-pins/SKILL.md).
- When bumping Home Assistant, re-verify the internal APIs listed in [docs/design.md](docs/design.md#internal-apis) at the new tag.
- Use conventional commits with imperative subjects: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, or `chore:`.

## Commits and tests

- Commit messages: `<type>(<optional-scope>): <imperative subject>`, body explains why. Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`. Details: [conventional-commits](.claude/skills/conventional-commits/SKILL.md).
- Tests under `tests/`: assert real Home Assistant behavior (no tautological tests), use the `integration` fixture (real Local Calendar), keep the autouse `enable_custom_integrations` fixture. Details: [python-tests](.claude/skills/python-tests/SKILL.md).

## Required verification

```bash
/home/vscode/.venv/bin/python -m pytest
/home/vscode/.venv/bin/python -m ruff check .
```

Use focused pytest selection while iterating, then run the full suite. New user-visible integration behavior needs tests in the same change. The Linux Dev Container is the authoritative local environment; GitHub Actions CI must stay green on `main` / PRs.

## Change hygiene

- User-visible integration, action, config-flow, or security behavior belongs in `CHANGELOG.md`. Internal refactors, CI, tests, docs-only edits, and agent tooling do not. Follow [Contributing](CONTRIBUTING.md#changelog-policy).
- Update README together when described setup or behavior changes.
- Keep GitHub Actions and tool versions exactly pinned when workflows exist (`@vN.N.N` by default; see [ci-pins](.claude/skills/ci-pins/SKILL.md) for the `hacs/action` and hassfest SHA exceptions).
- Pull request summaries cover the full branch and list verification.
