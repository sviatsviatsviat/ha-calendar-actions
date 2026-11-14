---
name: python-tests
description: Test Calendar Actions config flow, setup, and services with pytest-homeassistant-custom-component. Use when adding tests, reviewing test quality, or implementing integration behavior.
---

# Python tests

Follow [AGENTS.md](../../../AGENTS.md) and the current patterns under `tests/`.

## Layers

| Layer | Location | Rule |
|---|---|---|
| Unit / integration | `tests/` | Use HA test harness; call the services and assert the events a real Local Calendar returns. |
| Manual HA run | `config/` via debug/task | Smoke-check UI and live reload; not a substitute for pytest. |

## General rules

- Assert observable Home Assistant behavior; no placeholder or tautological tests.
- Keep the autouse `enable_custom_integrations` fixture in `tests/conftest.py`.
- Prefer `MockConfigEntry` and full `async_setup` / unload paths for service tests.
- Use focused patches for collaborators; avoid over-mocking HA internals.
- Exercise services against a real `local_calendar` entry stored under `tmp_path`; do not replace it with a fake calendar entity.
- Freeze time (`freezer`) and use the Europe/Warsaw time zone fixture so recurrence and DST expectations are deterministic.
- Name tests after the behavior under test (`test_single_instance_update_keeps_other_instances`).

## Config flow and setup

Cover as applicable:

- successful create/abort paths;
- `single_config_entry` rejection of a second entry;
- service registration;
- each update/delete mode (whole series, single instance, THISANDFUTURE);
- rejected inputs and permission checks;
- clean unload / reload behavior.

## Verification

```bash
/home/vscode/.venv/bin/python -m pytest
/home/vscode/.venv/bin/python -m pytest tests/test_update.py -q
/home/vscode/.venv/bin/python -m ruff check .
```
