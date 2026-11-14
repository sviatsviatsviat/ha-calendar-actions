"""Tests for update_event partial patches."""

from datetime import timedelta

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import call, create_weekly_series, list_events

SERIES_STARTS = [
    "2026-10-19T19:00:00+02:00",
    "2026-10-26T19:00:00+01:00",
    "2026-11-02T19:00:00+01:00",
    "2026-11-09T19:00:00+01:00",
]


async def test_whole_series_patch_keeps_series_start(
    hass: HomeAssistant, integration: MockConfigEntry
) -> None:
    """Patching only the summary renames every instance and keeps the times."""
    uid = await create_weekly_series(hass)

    await call(hass, "update_event", uid=uid, summary="Swim class")

    events = await list_events(hass)
    assert [event["start"] for event in events] == SERIES_STARTS
    assert {event["summary"] for event in events} == {"Swim class"}
    assert {event["location"] for event in events} == {"Pool"}
    assert {event["rrule"] for event in events} == {"FREQ=WEEKLY;COUNT=4"}


async def test_whole_series_new_start_keeps_duration(
    hass: HomeAssistant, integration: MockConfigEntry
) -> None:
    """A new dtstart without dtend moves the series and keeps its duration."""
    uid = await create_weekly_series(hass)

    await call(hass, "update_event", uid=uid, dtstart="2026-10-19T18:00:00+02:00")

    events = await list_events(hass)
    assert [event["start"][11:16] for event in events] == ["18:00"] * 4
    assert [event["end"][11:16] for event in events] == ["19:00"] * 4


async def test_whole_series_new_rule(
    hass: HomeAssistant, integration: MockConfigEntry
) -> None:
    """The recurrence rule of a series can be replaced."""
    uid = await create_weekly_series(hass)

    await call(hass, "update_event", uid=uid, rrule="FREQ=WEEKLY;COUNT=2")

    events = await list_events(hass)
    assert [event["start"] for event in events] == SERIES_STARTS[:2]


async def test_single_instance(
    hass: HomeAssistant, integration: MockConfigEntry
) -> None:
    """recurrence_id alone changes only that instance."""
    uid = await create_weekly_series(hass)
    second = (await list_events(hass))[1]

    await call(
        hass,
        "update_event",
        uid=uid,
        recurrence_id=second["recurrence_id"],
        summary="Swimming (late)",
        dtstart="2026-10-26T20:00:00+01:00",
    )

    events = await list_events(hass)
    assert [event["summary"] for event in events] == [
        "Swimming",
        "Swimming (late)",
        "Swimming",
        "Swimming",
    ]
    assert events[1]["start"] == "2026-10-26T20:00:00+01:00"
    assert events[1]["end"] == "2026-10-26T21:00:00+01:00"
    assert events[1]["location"] == "Pool"
    assert [events[i]["start"] for i in (0, 2, 3)] == [
        SERIES_STARTS[i] for i in (0, 2, 3)
    ]


async def test_moved_instance_is_found_again(
    hass: HomeAssistant, integration: MockConfigEntry
) -> None:
    """An instance moved away from its recurrence_id can still be updated."""
    uid = await create_weekly_series(hass)
    second = (await list_events(hass))[1]
    target = {"uid": uid, "recurrence_id": second["recurrence_id"]}

    await call(hass, "update_event", **target, dtstart="2026-10-31T10:00:00+01:00")
    await call(hass, "update_event", **target, summary="Moved")

    moved = next(e for e in await list_events(hass) if e["summary"] == "Moved")
    assert moved["start"] == "2026-10-31T10:00:00+01:00"


async def test_this_and_future(
    hass: HomeAssistant, integration: MockConfigEntry
) -> None:
    """THISANDFUTURE changes the instance and all following ones."""
    uid = await create_weekly_series(hass)
    third = (await list_events(hass))[2]

    await call(
        hass,
        "update_event",
        uid=uid,
        recurrence_id=third["recurrence_id"],
        recurrence_range="THISANDFUTURE",
        summary="Advanced swimming",
    )

    events = await list_events(hass)
    assert [event["start"] for event in events] == SERIES_STARTS
    assert [event["summary"] for event in events] == [
        "Swimming",
        "Swimming",
        "Advanced swimming",
        "Advanced swimming",
    ]


async def test_single_event_patch(
    hass: HomeAssistant, integration: MockConfigEntry
) -> None:
    """A non-recurring event keeps the fields that are not passed."""
    await call(
        hass,
        "create_event",
        summary="Dentist",
        dtstart="2026-10-20T09:00:00+02:00",
        dtend="2026-10-20T10:00:00+02:00",
        description="Check-up",
        location="Clinic",
    )
    uid = (await list_events(hass))[0]["uid"]

    await call(hass, "update_event", uid=uid, location="New clinic")

    assert await list_events(hass) == [
        {
            "uid": uid,
            "summary": "Dentist",
            "start": "2026-10-20T09:00:00+02:00",
            "end": "2026-10-20T10:00:00+02:00",
            "description": "Check-up",
            "location": "New clinic",
        }
    ]


async def test_series_older_than_window_needs_start(
    hass: HomeAssistant,
    integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A series that may start before the search window requires dtstart."""
    await call(
        hass,
        "create_event",
        summary="Bins",
        dtstart="2026-10-19T07:00:00+02:00",
        dtend="2026-10-19T07:30:00+02:00",
        rrule="FREQ=WEEKLY",
    )
    uid = (await list_events(hass))[0]["uid"]
    freezer.tick(timedelta(days=7 * 366))

    with pytest.raises(ServiceValidationError) as err:
        await call(hass, "update_event", uid=uid, summary="Rubbish")
    assert err.value.translation_key == "series_start_unknown"

    await call(
        hass,
        "update_event",
        uid=uid,
        summary="Rubbish",
        dtstart="2026-10-19T07:00:00+02:00",
        dtend="2026-10-19T07:30:00+02:00",
    )
    events = await list_events(hass)
    assert events[0]["summary"] == "Rubbish"
    assert events[0]["start"] == "2026-10-19T07:00:00+02:00"


async def test_unknown_uid(hass: HomeAssistant, integration: MockConfigEntry) -> None:
    """Updating a uid that does not exist is a validation error."""
    with pytest.raises(ServiceValidationError) as err:
        await call(hass, "update_event", uid="missing", summary="x")
    assert err.value.translation_key == "event_not_found"


async def test_nothing_to_update(
    hass: HomeAssistant, integration: MockConfigEntry
) -> None:
    """At least one event field is required."""
    uid = await create_weekly_series(hass)
    with pytest.raises(ServiceValidationError) as err:
        await call(hass, "update_event", uid=uid)
    assert err.value.translation_key == "nothing_to_update"


async def test_whole_series_new_rule_with_new_start(
    hass: HomeAssistant, integration: MockConfigEntry
) -> None:
    """A new rule and start together replace the series from its first instance."""
    uid = await create_weekly_series(hass)

    await call(
        hass,
        "update_event",
        uid=uid,
        dtstart="2026-10-20T19:00:00+02:00",
        rrule="FREQ=WEEKLY;BYDAY=TU;COUNT=2",
    )

    events = await list_events(hass)
    assert [event["start"] for event in events] == [
        "2026-10-20T19:00:00+02:00",
        "2026-10-27T19:00:00+01:00",
    ]


async def test_empty_string_clears_field(
    hass: HomeAssistant, integration: MockConfigEntry
) -> None:
    """An empty description clears it on the whole series."""
    uid = await create_weekly_series(hass)
    await call(hass, "update_event", uid=uid, description="Bring goggles")
    assert {e.get("description") for e in await list_events(hass)} == {"Bring goggles"}

    await call(hass, "update_event", uid=uid, description="")
    assert {e.get("description") for e in await list_events(hass)} <= {None, ""}
