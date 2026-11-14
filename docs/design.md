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
- **Partial update.** `update_event` fetches the current event and merges in the given fields before validating, because the entity API replaces the whole event. A recurring event is only updated from a known instance (see below).
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

The entity API (`async_get_events`) exposes instances, not a series' original DTSTART, and a calendar applies a whole-series edit to the start it is given. Inferring the start from the earliest visible instance is unsafe. A deleted first instance (EXDATE) makes a later instance look like the start, so a COUNT series gains an extra date. An old series that started before any search window loses its history. For Local Calendar (`ical` `EventStore.edit`), a whole-series edit also replaces every stored item with that uid, so individually changed (detached) instances disappear. So:

- The current event is found among the instances in the window (now −5 years … now +5 years) with the same `uid`, then by `recurrence_id`.
- **No `recurrence_id`:** allowed only for a non-recurring event. For a recurring one the service raises `series_update_requires_instance` before any change.
- **`recurrence_id` alone:** edits that instance. The rule is not sent; Local Calendar rejects a different rule on a single instance.
- **`recurrence_id` + `THISANDFUTURE`:** `ical` splits the series at that instance and adjusts COUNT. From the true first instance it is a whole-series edit. If that instance is the earliest visible one (possibly the series start) and the series has detached instances (`recurrence_id` set, no `rrule`), the service raises `series_has_changed_instances` before any change. From a later instance, detached instances are kept with their own values.
- `dtstart` without `dtend` keeps the duration.
- A rule can't be removed by omitting it: Local Calendar keeps fields that are not set.
- Create, update and delete run under a per-calendar `asyncio.Lock`, so a concurrent call can't write between update_event's read and write.

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
