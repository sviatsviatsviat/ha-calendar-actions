# Design

This document records why Calendar Actions exists, the constraints already settled, and the Home Assistant internals it relies on. For user-facing behavior see the [README](../README.md); for the workflow see [CONTRIBUTING.md](../CONTRIBUTING.md).

## Why it exists

As of Home Assistant 2026.10:

- **Recurrence:** `calendar.create_event` does not accept `rrule`. Recurrence is only available through the WebSocket command `calendar/event/create`.
- **Edit/delete:** there are no services, only the WebSocket commands `calendar/event/update` and `calendar/event/delete`.
- **Finding events:** the `calendar.get_events` response does not include `uid`, `recurrence_id` or `rrule` (`LIST_EVENT_FIELDS` is start, end, summary, description, location, status), so automations can't identify which event to edit or delete.

## Settled decisions

- **In-process calls.** Services call the calendar entity methods directly, exactly like the WebSocket handlers in `homeassistant/components/calendar/__init__.py`. No HTTP, token or `shell_command`.
- **Rejected:** `python_script` (its sandbox blocks `async_*` calls and entity access).
- **Own domain.** Services are `calendar_actions.*`, not entity services in the `calendar` domain. Their descriptions show in the UI without `async_set_service_schema`, and their names can't collide with future HA services.
- **Config flow only.** It's a single-instance, no-field config flow so the integration appears in Devices & services. `CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)`. Services are registered in `async_setup`.
- **Partial update.** `update_event` fetches the current event and merges in the given fields before validating, because the entity API replaces the whole event.
- **Minimum Home Assistant 2026.10.0.** Validation uses Probatio (`import probatio`; HA replaced voluptuous in 2026.9).

## Per-call checks

Every service, in this order:

1. `entity_id` validated with `cv.entity_domain("calendar")`.
2. If `call.context.user_id` is set: look up the user (`UnknownUser` if missing), then `user.permissions.check_entity(entity_id, policy)` → `Unauthorized`. The policy is `POLICY_CONTROL` for create/update/delete and `POLICY_READ` for list.
3. Entity from `hass.data[DATA_COMPONENT].get_entity(entity_id)` → `ServiceValidationError` if it is missing or not `available`.
4. Feature check against `entity.supported_features` (`CalendarEntityFeature`).
5. `entity.async_set_context(call.context)` before mutating.
6. Errors from `WEBSOCKET_EVENT_SCHEMA` — `probatio.Invalid`, `ValueError`, `TypeError` — become `ServiceValidationError`. HA's rrule validator raises plain exceptions for some malformed rules, such as a part without `=`. Backend `probatio.Invalid`/`ValueError` (for example from Local Calendar's event parsing) also become `ServiceValidationError`. Backend `HomeAssistantError`s propagate unchanged.

Before validation, start and end are parsed and moved to the local time zone. `WEBSOCKET_EVENT_SCHEMA` requires both values to share one `tzinfo`, so `+02:00`/`+01:00` across a DST change would otherwise be rejected.

## update_event lookup and merge

- With `recurrence_id`, the instance is searched within ±2 days of the instant the `recurrence_id` names, then in the wide window (an instance may have been moved).
- Without `recurrence_id`, the earliest instance in the wide window (now −5 years … now +5 years) stands for the event or series.
- For a whole-series update whose times come from that instance, or that replaces the rule, the first visible instance must be the real series start. If the gap from the window start to that instance is shorter than the gap between the first two instances, an earlier instance may exist outside the window. The service then raises `series_start_unknown` and asks for `dtstart`/`dtend` rather than truncating the series.
- `dtstart` without `dtend` keeps the duration.
- For a single-instance edit, the rule is not sent. Local Calendar rejects a different rule on a single instance.
- A changed rule for the whole series is sent as an edit of the first instance with `THISANDFUTURE`. Local Calendar (`ical` `EventStore.edit`) refuses a changed rule on a plain series edit. RFC 5545 treats THISANDFUTURE from the first instance as the whole series, and `ical` handles it that way.
- A rule can't be removed by omitting it: Local Calendar keeps fields that are not set.

## Internal APIs

These are not public and may move between releases. Verified against `homeassistant==2026.10.4`:

| Name | Module |
|---|---|
| `WEBSOCKET_EVENT_SCHEMA`, `CalendarEntity`, `CalendarEvent` | `homeassistant.components.calendar` |
| `DATA_COMPONENT`, `CalendarEntityFeature`, `DOMAIN`, `EVENT_UID`, `EVENT_RECURRENCE_ID`, `EVENT_RECURRENCE_RANGE`, `EVENT_START`, `EVENT_END`, `EVENT_SUMMARY`, `EVENT_DESCRIPTION`, `EVENT_LOCATION`, `EVENT_RRULE` | `homeassistant.components.calendar.const` |
| `POLICY_CONTROL`, `POLICY_READ` | `homeassistant.auth.permissions.const` |

Entity methods used: `async_get_events(hass, start, end)`, `async_create_event(**event)`, `async_update_event(uid, event, recurrence_id=, recurrence_range=)`, `async_delete_event(uid, recurrence_id=, recurrence_range=)`.

Upstream `dev` has been splitting the calendar component into `helper.py`, `services.py` and `entity.py`. On every Home Assistant bump, re-read these modules at the new tag and update the imports and this table.

## Startup safety

No lazy imports and no `try`-wrapped imports. If an import fails (for example a moved internal API), Home Assistant isolates it: `loader._get_component` converts the exception to `ImportError`, `setup._async_setup_component` logs `Setup failed for custom integration 'calendar_actions'`, and Home Assistant keeps booting.

Manual check after changing imports:

1. In a scratch copy of `config/`, add a deliberately broken import to `custom_components/calendar_actions/__init__.py` (e.g. `from homeassistant.components.calendar import DOES_NOT_EXIST`).
2. Run `python -m homeassistant -c <dir>`. Without `home-assistant-frontend` installed, Home Assistant starts in recovery mode, which is fine for this check.
3. Confirm Home Assistant keeps running and logs only the "Setup failed for custom integration 'calendar_actions'" error for this integration.
