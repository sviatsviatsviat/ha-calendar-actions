# Changelog

All notable user-visible changes to the Calendar Actions Home Assistant integration are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The project intends to use [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-11-14

### Added

- Requires Home Assistant 2026.10.0 or newer (enforced via HACS).
- **Calendar Actions** integration (`calendar_actions`), added from the UI; a single entry is allowed.
- `calendar_actions.create_event`: creates an event on a calendar, optionally recurring via an RFC 5545 rule (daily or less frequent).
- `calendar_actions.list_events`: lists events in a time range with `uid`, `recurrence_id` and `rrule`.
- `calendar_actions.update_event`: changes only the given fields of an event, a single instance of a recurring event, or an instance and all following ones. Edits that would shift a series or drop its individually changed instances are refused before anything changes.
- `calendar_actions.delete_event`: deletes a whole event or series, a single instance, or an instance and all following ones.
- Actions check the calling user's calendar permissions and report invalid input and unsupported calendars as validation errors.
