![Calendar Actions](custom_components/calendar_actions/brand/logo.png)

# Calendar Actions for Home Assistant

Home Assistant custom integration that adds the calendar actions the built-in `calendar.*` actions lack: create **recurring** events, **update** and **delete** events (a whole series, one instance, or an instance and all following ones), and **list** events with the identifiers needed to do that. The actions work from scripts, automations and Assist (LLM).

It calls calendar entities in-process, the same way the Home Assistant calendar UI does over the WebSocket API. No tokens, HTTP calls or shell commands.

> **This is not an official Home Assistant integration.** It is an independent project and is not affiliated with, endorsed by, or supported by the Home Assistant project.

## Installation

Requires Home Assistant **2026.10.0** or newer (enforced by HACS).

### HACS (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=sviatsviatsviat&repository=ha-calendar-actions&category=integration)

1. Install [HACS](https://hacs.xyz/) if it is not already installed.
2. In Home Assistant, open **HACS**.
3. Use the badge above, or add this repository as a custom repository:
   - Menu (⋮) → **Custom repositories**
   - Repository: `https://github.com/sviatsviatsviat/ha-calendar-actions`
   - Category: **Integration**
4. Find **Calendar Actions**, select **Download**, then restart Home Assistant.

### Manual

1. Copy `custom_components/calendar_actions` into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.

## Configuration

1. Go to **Settings → Devices & services**.
2. Select **Add integration** and search for **Calendar Actions**.
3. Confirm. There is nothing to configure, and only one entry is allowed.

The actions work with any calendar entity that supports the operation (create, update or delete). They are tested with [Local Calendar](https://www.home-assistant.io/integrations/local_calendar/). A calendar without the needed feature is rejected with a clear error.

## Actions

Dates and times use ISO 8601. A date (`2026-10-26`) makes an all-day event, where the end is the day after the last day. A date-time should carry an offset (`2026-10-26T19:00:00+01:00`); one without an offset is read as Home Assistant's local time. Start and end must be the same type, and the end must be after the start.

`rrule` is an [RFC 5545](https://datatracker.ietf.org/doc/html/rfc5545#section-3.3.10) recurrence rule without the `RRULE:` prefix. `FREQ` is required and must be `DAILY`, `WEEKLY`, `MONTHLY` or `YEARLY`. Examples:

| Rule | Meaning |
|---|---|
| `FREQ=WEEKLY;BYDAY=MO` | Every Monday |
| `FREQ=WEEKLY;INTERVAL=2;BYDAY=TU,TH` | Tuesday and Thursday every other week |
| `FREQ=MONTHLY;BYDAY=3SA` | Third Saturday of each month |
| `FREQ=DAILY;COUNT=10` | Ten days in a row |
| `FREQ=YEARLY;UNTIL=20301231` | Every year until the end of 2030 |

Recurring events keep their local wall-clock time across daylight-saving changes.

### `calendar_actions.create_event`

| Field | Required | Description |
|---|---|---|
| `entity_id` | yes | Calendar entity |
| `summary` | yes | Title |
| `dtstart` | yes | Start date or date-time |
| `dtend` | yes | End date or date-time |
| `rrule` | no | Recurrence rule |
| `description` | no | Description |
| `location` | no | Location |

```yaml
action: calendar_actions.create_event
data:
  entity_id: calendar.family
  summary: Swimming
  dtstart: "2026-10-19T19:00:00+02:00"
  dtend: "2026-10-19T20:00:00+02:00"
  rrule: FREQ=WEEKLY;BYDAY=MO
```

### `calendar_actions.list_events`

Returns the events in a range, including `uid`, `recurrence_id` and `rrule`. `calendar.get_events` does not return these, and update/delete need them.

| Field | Required | Description |
|---|---|---|
| `entity_id` | yes | Calendar entity |
| `start` | no | Range start; defaults to now |
| `end` | one of `end` / `duration` | Range end |
| `duration` | one of `end` / `duration` | Range length from `start` |

```yaml
action: calendar_actions.list_events
data:
  entity_id: calendar.family
  duration:
    days: 14
response_variable: result
```

Response:

```yaml
events:
  - uid: 6f0c…
    recurrence_id: "20261026T190000"
    rrule: FREQ=WEEKLY;BYDAY=MO
    summary: Swimming
    start: "2026-10-26T19:00:00+01:00"
    end: "2026-10-26T20:00:00+01:00"
```

Fields without a value are left out. A non-recurring event has no `recurrence_id` or `rrule`.

### `calendar_actions.update_event`

Changes only the fields you pass. Everything else stays as it is.

| Field | Required | Description |
|---|---|---|
| `entity_id` | yes | Calendar entity |
| `uid` | yes | `uid` from `list_events` |
| `recurrence_id` | recurring events | `recurrence_id` from `list_events` (see the modes below) |
| `recurrence_range` | no | `THISANDFUTURE` (needs `recurrence_id`) |
| `summary`, `dtstart`, `dtend`, `rrule`, `description`, `location` | at least one | New values |

- If you pass `dtstart` without `dtend`, the event keeps its duration.
- An empty `description` or `location` clears it.
- **A recurring event always needs `recurrence_id`.** Change one instance (`recurrence_id` alone), or an instance and everything after it (`recurrence_id` + `THISANDFUTURE`). To change the whole series, use its first instance with `THISANDFUTURE`. Calendars don't report a series' original start, so the action never guesses it: a guess could shift the series or drop past instances.
- If a series has individually changed instances (for example one moved to another day), `THISANDFUTURE` from its earliest instance is refused, because the calendar would remove those changed instances. Start from a later instance, or update the changed instances separately. Changed instances keep their own values when the rest of the series changes.
- A new `rrule` for a recurring event needs `THISANDFUTURE`.
- A recurrence rule can't be removed from a series, because calendars keep the existing rule. To end a series, set `UNTIL`/`COUNT` or delete the remaining instances.
- Updates to the same calendar run one at a time, so concurrent patches of different fields don't overwrite each other.

```yaml
action: calendar_actions.update_event
data:
  entity_id: calendar.family
  uid: "{{ event.uid }}"
  recurrence_id: "{{ event.recurrence_id }}"
  summary: Swimming (moved)
  dtstart: "2026-10-26T20:00:00+01:00"
```

### `calendar_actions.delete_event`

| Field | Required | Description |
|---|---|---|
| `entity_id` | yes | Calendar entity |
| `uid` | yes | `uid` from `list_events` |
| `recurrence_id` | no | `recurrence_id` from `list_events` |
| `recurrence_range` | no | `THISANDFUTURE` (needs `recurrence_id`) |

### Update and delete modes

| `recurrence_id` | `recurrence_range` | Applies to |
|---|---|---|
| — | — | Delete: the whole event or series. Update: a non-recurring event only |
| set | — | That single instance |
| set | `THISANDFUTURE` | That instance and all following ones (the whole series from its first instance) |

`recurrence_range` without `recurrence_id` is rejected, so a mistake can't silently affect a whole series.

### Permissions and errors

When an action is called with a user context (for example from the UI or Assist), the user needs control permission on the calendar for create/update/delete and read permission for list. Invalid input, unknown calendars, unsupported features and events that can't be found are reported as validation errors. Errors from the calendar itself are passed through.

## Assist

Assist (and other LLM agents) can use these actions through scripts exposed to Assist. The script description tells the model how to fill the fields. For example:

```yaml
create_recurring_calendar_event:
  alias: Create recurring calendar event
  description: >
    Creates a recurring event in the family calendar. rrule: RFC 5545 without
    "RRULE:" prefix, e.g. FREQ=WEEKLY;BYDAY=MO | FREQ=WEEKLY;INTERVAL=2;BYDAY=TU,TH
    | FREQ=MONTHLY;BYDAY=3SA | FREQ=DAILY;COUNT=10.
  fields:
    summary:
      required: true
      selector:
        text:
    start:
      description: Start date and time
      required: true
      selector:
        datetime:
    duration_minutes:
      required: true
      selector:
        number:
          min: 1
          max: 1440
    rrule:
      required: true
      selector:
        text:
  sequence:
    - action: calendar_actions.create_event
      data:
        entity_id: calendar.family
        summary: "{{ summary }}"
        dtstart: "{{ as_local(as_datetime(start)).isoformat() }}"
        dtend: >-
          {{ (as_local(as_datetime(start))
              + timedelta(minutes=duration_minutes | int)).isoformat() }}
        rrule: "{{ rrule }}"
```

To change or delete events, expose a script that calls `list_events` and returns the response. Then expose scripts that call `update_event` / `delete_event` with the `uid` and `recurrence_id` the model read from that list:

```yaml
list_calendar_events:
  alias: List calendar events
  description: >
    Lists family calendar events in the next N days with uid and recurrence_id,
    needed to update or delete an event.
  fields:
    days:
      required: true
      selector:
        number:
          min: 1
          max: 365
  sequence:
    - action: calendar_actions.list_events
      data:
        entity_id: calendar.family
        duration:
          days: "{{ days | int }}"
      response_variable: result
    - stop: Done
      response_variable: result
```

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow, [CHANGELOG.md](CHANGELOG.md) for user-visible release notes, and [docs/design.md](docs/design.md) for design constraints and the Home Assistant internals this integration relies on.
