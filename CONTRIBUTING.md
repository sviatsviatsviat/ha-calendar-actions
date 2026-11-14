# Contributing to Calendar Actions

Changes are expected to keep code, tests, user documentation, and the changelog aligned. Start with [README](README.md) for shipped actions and end-user setup, then use this guide for the development workflow. Agents should also follow [AGENTS.md](AGENTS.md).

## Development environment

The project requires Python **3.14.2+** (see `pyproject.toml`).

Use the pinned Linux [Dev Container](.devcontainer/) for the authoritative verification suite.

1. Install Docker, Visual Studio Code, and the **Dev Containers** extension.
2. Open this repository in Visual Studio Code.
3. Run **Dev Containers: Reopen in Container** from the Command Palette.
4. Wait for the post-create setup to install the pinned dependencies.

After creating the container, dependencies install into `/home/vscode/.venv`, and `config/custom_components` is symlinked to the repo `custom_components/` tree. Home Assistant therefore loads edits directly; there is no copy step. The Python virtual environment lives on the container's native Linux filesystem, avoiding slow virtualenv I/O on Windows bind mounts.

A local venv is fine for editing and focused tests, but keep pins identical to `requirements-dev.txt`.

Before submitting a change:

```bash
/home/vscode/.venv/bin/python -m pytest
/home/vscode/.venv/bin/python -m ruff check .
```

GitHub Actions (`.github/workflows/ci.yml`) runs Python lint/tests on every push and pull request to `main`. Validation (`.github/workflows/validate.yml`) runs hassfest and the HACS Action on the same events plus a daily schedule. Dependabot (`.github/dependabot.yml`) opens weekly PRs for GitHub Actions, pip pins, Dev Container features, and the Dev Container base image. Pip updates for `homeassistant` and `pytest-homeassistant-custom-component` are grouped so they stay compatible; bump `hacs.json` `homeassistant` and the README minimum in the same change.

Do not point development at a production Home Assistant install.

## Run Home Assistant

Run the **Home Assistant: Run** task with **Terminal: Run Task**, or run:

```bash
/home/vscode/.venv/bin/python -m homeassistant -c config
```

Open [http://localhost:8123](http://localhost:8123), complete Home Assistant's first-run onboarding, then:

1. Go to **Settings → Devices & services**.
2. Select **Add integration**, add a **Local Calendar** to test against.
3. Select **Add integration** again and add **Calendar Actions**.
4. Call the actions from **Developer tools → Actions** (`calendar_actions.*`).

All generated Home Assistant state is stored in `config/` and ignored by Git. This setup does not use or modify a production Home Assistant installation.

## Test and lint

Use the **Tests** and **Lint** VS Code tasks, or run inside the container:

```bash
/home/vscode/.venv/bin/python -m pytest
/home/vscode/.venv/bin/python -m ruff check .
```

To debug Home Assistant, open **Run and Debug**, select **Home Assistant**, and start it. Breakpoints in `custom_components/calendar_actions` are loaded directly.

## Find the right place

| Change | Primary location |
|---|---|
| Setup / service registration | `custom_components/calendar_actions/__init__.py` |
| Config flow | `custom_components/calendar_actions/config_flow.py` |
| Service schemas and handlers | `custom_components/calendar_actions/services.py` |
| Constants / domain / search windows | `custom_components/calendar_actions/const.py` |
| Service field selectors and examples | `custom_components/calendar_actions/services.yaml` |
| Strings (config flow, services, errors) | `translations/en.json` (do not use `strings.json`) |
| Manifest / HACS metadata | `manifest.json`, `hacs.json` |
| Tests | `tests/` |
| Dev Container / editor | `.devcontainer/`, `.vscode/` |
| Pins and tool config | `requirements-dev.txt`, `pyproject.toml` |

Integration code lives only under `custom_components/calendar_actions/`. Do not copy sources into `config/`; rely on the symlink created by the Dev Container.

## Implementing changes

### User-visible integration changes

- Call calendar entities in-process, exactly like the calendar WebSocket handlers do; validate events with the calendar component's `WEBSOCKET_EVENT_SCHEMA`.
- Keep the per-call checks described in [docs/design.md](docs/design.md#per-call-checks) for every service.
- Do not use lazy or `try`-wrapped imports (see [docs/design.md](docs/design.md#startup-safety)).
- Add or update pytest coverage for each service mode and rejected input.
- Update [README](README.md) and [CHANGELOG.md](CHANGELOG.md) in the same change when users can observe the behavior.

### Internal changes

Internal refactors still need tests when behavior or invariants can regress. They do not need a changelog entry unless users observe a change.

### Tooling and environment changes

Keep Dev Container, VS Code tasks/launch settings, and this guide's commands consistent with the venv path and verification commands. Pin exact package versions in `requirements-dev.txt`.

## Tests

Tests must assert Home Assistant behavior rather than implementation bookkeeping.

| Layer | Location | Scope |
|---|---|---|
| Automated | `tests/` | `pytest-homeassistant-custom-component`; services against a real Local Calendar |
| Manual | `config/` via task/debugger | UI setup, Developer tools action calls, startup safety |

- Keep the autouse `enable_custom_integrations` fixture in `tests/conftest.py`.
- Use the `integration` fixture: a real `local_calendar` entry stored under `tmp_path`, Europe/Warsaw time zone, frozen time.
- Assert through `list_events` what the calendar actually holds after each action.
- Name tests after the behavior under test.

Run a focused pytest selection while iterating, then the complete verification suite before handoff.

`ical` is pinned in `requirements-dev.txt` to the version Local Calendar requires in the pinned Home Assistant release, because the test harness does not install integration requirements. Bump it together with `homeassistant`.

### Startup safety (manual)

When changing imports in `__init__.py` or `services.py`, follow the startup-safety check in [docs/design.md](docs/design.md#startup-safety).

## Documentation

User-facing behavior has two primary documentation layers:

1. [README](README.md) for HACS/manual install, configuration, and actions;
2. [CHANGELOG.md](CHANGELOG.md) for release-level outcomes.

Development setup, verification, and contribution policy live in this guide. Update affected layers in the same pull request. Avoid documenting planned actions or fields as if they already ship.

Design constraints and the Home Assistant internals this integration depends on are documented in [docs/design.md](docs/design.md). Keep it aligned when a Home Assistant bump moves or changes those internals.

Module and function docstrings should be short complete sentences that describe behavior. Follow existing style in `custom_components/calendar_actions/`.

## Changelog policy

The changelog is for behavior available to Home Assistant users:

- config flow steps, options, and abort reasons;
- actions (services), their fields, and response fields;
- setup/unload/reload behavior that affects the UI or automations;
- security fixes.

Do not add entries for repository scaffolding, CI, lint configuration, tests, agent instructions, documentation-only edits, or internal refactors with no visible effect. Entries should describe what a user can do and the behavior they can rely on.

Use Keep a Changelog sections. Until there is a published baseline beyond the initial stub, describe new shipped behavior under `Added`; use `Changed` or `Removed` only relative to behavior users could obtain from a tagged release.

## Version pinning

Python package pins in `requirements-dev.txt`, Dev Container feature versions (for example GitHub CLI in `.devcontainer/devcontainer.json`), and GitHub Action versions are exact. Never introduce `@latest`, branch tags, or floating major/minor Action tags.

Allowed workflow `uses:` pins:

- Exact `@vN.N.N` release tags (default).
- `hacs/action@N.N.N` only (HACS tags omit the `v` prefix).
- `home-assistant/actions/hassfest@` plus a full 40-character commit SHA only.

When bumping a dependency, update every reference to that same dependency in the same pull request (requirements, workflows, `hacs.json` `homeassistant` when the Home Assistant pin changes, `ical`, and docs that cite the version).

Audit every workflow `uses:` pin with the command in [`.claude/skills/ci-pins/SKILL.md`](.claude/skills/ci-pins/SKILL.md). It must exit 0 with no violations.

## Cutting a release

Releases are git tags. HACS installs from GitHub Releases (not PyPI). Keep `custom_components/calendar_actions/manifest.json` `version` and `pyproject.toml` `[project].version` aligned with the release as `X.Y.Z` (no `v`). Git tags use the `v` prefix (`vX.Y.Z`); changelog headings omit it (`## [X.Y.Z]`).

1. On `main`, promote `## [Unreleased]` in `CHANGELOG.md` to `## [X.Y.Z] - YYYY-MM-DD` (or a pre-release such as `0.1.0-alpha`), leave a fresh empty `## [Unreleased]`, set `manifest.json` and `pyproject.toml` versions to `X.Y.Z`, and merge after CI and validate are green. The heading version must match the tag without the leading `v`.
2. Create and push only the annotated tag on that `main` commit (`git tag -a vX.Y.Z && git push origin vX.Y.Z`). The release workflow refuses tags whose commit is not an ancestor of `origin/main`. Do not craft the Release body by hand; `.github/workflows/release.yml` fills notes from that changelog section via `.github/scripts/changelog-section.sh` (strips the tag’s leading `v` when looking up the heading).
3. Confirm the GitHub Release page. Pre-release tags (`vX.Y.Z-…`) are marked as GitHub prereleases.

## Commits and pull requests

Use an imperative conventional commit subject:

```text
feat(services): add THISANDFUTURE support to delete_event
fix(services): keep event duration when only dtstart changes
docs: explain config/custom_components symlink
```

Supported prefixes are `feat`, `fix`, `refactor`, `test`, `docs`, and `chore`. Use the body to explain why the change is needed when the subject is not enough.

A pull request should:

- summarize the full branch, not only the last commit;
- call out user-visible behavior and compatibility;
- list verification performed;
- include documentation and changelog updates when required;
- keep unrelated cleanup out of the change.
