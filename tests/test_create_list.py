"""Tests for create_event and list_events."""

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import call, create_weekly_series, list_events


async def test_weekly_series_keeps_local_time_across_dst(
    hass: HomeAssistant, integration: MockConfigEntry
) -> None:
    """A weekly series expands at 19:00 Warsaw time before and after DST ends."""
    uid = await create_weekly_series(hass, count=3)

    events = await list_events(hass)
    assert [event["start"] for event in events] == [
        "2026-10-19T19:00:00+02:00",
        "2026-10-26T19:00:00+01:00",
        "2026-11-02T19:00:00+01:00",
    ]
    assert [event["end"] for event in events] == [
        "2026-10-19T20:00:00+02:00",
        "2026-10-26T20:00:00+01:00",
        "2026-11-02T20:00:00+01:00",
    ]
    assert {event["uid"] for event in events} == {uid}
    assert all(event["rrule"] == "FREQ=WEEKLY;COUNT=3" for event in events)
    assert all(event["summary"] == "Swimming" for event in events)
    assert all(event["location"] == "Pool" for event in events)


async def test_list_events_returns_identifiers(
    hass: HomeAssistant, integration: MockConfigEntry
) -> None:
    """list_events returns uid and distinct recurrence_id per instance."""
    await create_weekly_series(hass, count=2)
    await call(
        hass,
        "create_event",
        summary="Dentist",
        dtstart="2026-10-20T09:00:00+02:00",
        dtend="2026-10-20T10:00:00+02:00",
        description="Check-up",
    )

    events = await list_events(hass)
    series = [event for event in events if event["summary"] == "Swimming"]
    single = next(event for event in events if event["summary"] == "Dentist")

    assert len({event["recurrence_id"] for event in series}) == 2
    assert single["uid"] not in {event["uid"] for event in series}
    assert "recurrence_id" not in single
    assert "rrule" not in single
    assert single["description"] == "Check-up"


async def test_all_day_event(hass: HomeAssistant, integration: MockConfigEntry) -> None:
    """Dates create an all-day event."""
    await call(
        hass,
        "create_event",
        summary="Holiday",
        dtstart="2026-11-11",
        dtend="2026-11-12",
        rrule="FREQ=YEARLY",
    )
    events = await list_events(hass)
    assert events == [
        {
            "uid": events[0]["uid"],
            "recurrence_id": "20261111",
            "rrule": "FREQ=YEARLY",
            "summary": "Holiday",
            "start": "2026-11-11",
            "end": "2026-11-12",
        }
    ]


@pytest.mark.parametrize(
    "window",
    [
        {"duration": {"days": 20}},
        {"start": "2026-10-19T00:00:00+02:00", "duration": "24:00:00"},
    ],
)
async def test_list_events_with_duration(
    hass: HomeAssistant, integration: MockConfigEntry, window: dict
) -> None:
    """A duration works instead of end; start defaults to now."""
    await create_weekly_series(hass, count=4)
    response = await call(hass, "list_events", **window)
    assert response is not None
    assert len(response["events"]) == 1
