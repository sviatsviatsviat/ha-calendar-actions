"""Regression tests: series edits must not lose or invent instances."""

import asyncio

import pytest
from homeassistant.components.calendar.const import DATA_COMPONENT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import CALENDAR_ENTITY_ID, call, create_weekly_series, list_events


async def test_series_update_without_instance_is_rejected(
    hass: HomeAssistant, integration: MockConfigEntry
) -> None:
    """A recurring series can't be patched as a whole; nothing changes."""
    uid = await create_weekly_series(hass)
    before = await list_events(hass)

    with pytest.raises(ServiceValidationError) as err:
        await call(hass, "update_event", uid=uid, summary="Renamed")
    assert err.value.translation_key == "series_update_requires_instance"
    assert await list_events(hass) == before


async def test_this_and_future_from_start_with_moved_instance_is_rejected(
    hass: HomeAssistant, integration: MockConfigEntry
) -> None:
    """Editing from the earliest instance would drop moved instances."""
    uid = await create_weekly_series(hass)
    events = await list_events(hass)
    await call(
        hass,
        "update_event",
        uid=uid,
        recurrence_id=events[2]["recurrence_id"],
        dtstart="2026-11-03T20:00:00+01:00",
    )
    before = await list_events(hass)

    with pytest.raises(ServiceValidationError) as err:
        await call(
            hass,
            "update_event",
            uid=uid,
            recurrence_id=before[0]["recurrence_id"],
            recurrence_range="THISANDFUTURE",
            summary="Renamed",
        )
    assert err.value.translation_key == "series_has_changed_instances"
    assert await list_events(hass) == before


async def test_this_and_future_keeps_later_moved_instance(
    hass: HomeAssistant, integration: MockConfigEntry
) -> None:
    """Splitting the series from a later instance keeps a moved instance."""
    uid = await create_weekly_series(hass)
    events = await list_events(hass)
    await call(
        hass,
        "update_event",
        uid=uid,
        recurrence_id=events[3]["recurrence_id"],
        dtstart="2026-11-10T20:00:00+01:00",
    )
    before = await list_events(hass)

    await call(
        hass,
        "update_event",
        uid=uid,
        recurrence_id=before[1]["recurrence_id"],
        recurrence_range="THISANDFUTURE",
        summary="Renamed",
    )

    after = await list_events(hass)
    assert [e["start"] for e in after] == [e["start"] for e in before]
    assert [e["summary"] for e in after] == [
        "Swimming",
        "Renamed",
        "Renamed",
        "Swimming",
    ]


async def test_this_and_future_after_deleting_first_instance(
    hass: HomeAssistant, integration: MockConfigEntry
) -> None:
    """No instance reappears or is added after the first one was deleted."""
    uid = await create_weekly_series(hass)
    events = await list_events(hass)
    await call(hass, "delete_event", uid=uid, recurrence_id=events[0]["recurrence_id"])
    before = await list_events(hass)

    await call(
        hass,
        "update_event",
        uid=uid,
        recurrence_id=before[0]["recurrence_id"],
        recurrence_range="THISANDFUTURE",
        summary="Renamed",
    )

    after = await list_events(hass)
    assert [e["start"] for e in after] == [e["start"] for e in before]
    assert {e["summary"] for e in after} == {"Renamed"}


async def test_old_irregular_series_keeps_history(
    hass: HomeAssistant, integration: MockConfigEntry
) -> None:
    """Renaming upcoming instances of an old series keeps its history."""
    await call(
        hass,
        "create_event",
        summary="Old",
        dtstart="2020-09-01T19:00:00+02:00",
        dtend="2020-09-01T20:00:00+02:00",
        rrule="FREQ=WEEKLY;BYDAY=TU,WE",
    )
    history_range = {
        "start": "2020-09-01T00:00:00+02:00",
        "end": "2020-09-10T00:00:00+02:00",
    }
    history = await list_events(hass, **history_range)
    upcoming = await list_events(hass, end="2026-10-15T00:00:00+02:00")

    await call(
        hass,
        "update_event",
        uid=upcoming[0]["uid"],
        recurrence_id=upcoming[0]["recurrence_id"],
        recurrence_range="THISANDFUTURE",
        summary="Renamed",
    )

    old = await list_events(hass, **history_range)
    assert [(e["start"], e["summary"]) for e in old] == [
        (e["start"], e["summary"]) for e in history
    ]
    after = await list_events(hass, end="2026-10-15T00:00:00+02:00")
    assert [e["start"] for e in after] == [e["start"] for e in upcoming]
    assert {e["summary"] for e in after} == {"Renamed"}


async def test_concurrent_partial_updates_keep_both_fields(
    hass: HomeAssistant,
    integration: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two concurrent patches of different fields both take effect."""
    await call(
        hass,
        "create_event",
        summary="Dentist",
        dtstart="2026-10-20T09:00:00+02:00",
        dtend="2026-10-20T10:00:00+02:00",
        location="Clinic",
    )
    uid = (await list_events(hass))[0]["uid"]
    entity = hass.data[DATA_COMPONENT].get_entity(CALENDAR_ENTITY_ID)
    original = entity.async_get_events

    async def slow_read(*args, **kwargs):
        events = await original(*args, **kwargs)
        # Yield so an unserialized second update would read the same state.
        for _ in range(5):
            await asyncio.sleep(0)
        return events

    monkeypatch.setattr(entity, "async_get_events", slow_read)
    await asyncio.gather(
        call(hass, "update_event", uid=uid, summary="Dentist (moved)"),
        call(hass, "update_event", uid=uid, location="New clinic"),
    )

    [event] = await list_events(hass)
    assert event["summary"] == "Dentist (moved)"
    assert event["location"] == "New clinic"
