"""Shared fixtures for Calendar Actions tests."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import Context, HomeAssistant, ServiceResponse
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.calendar_actions.const import DOMAIN

CALENDAR_ENTITY_ID = "calendar.family"
TIME_ZONE = "Europe/Warsaw"
NOW = "2026-10-01T12:00:00+02:00"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading custom integrations in all tests."""


@pytest.fixture
async def local_calendar(
    hass: HomeAssistant, tmp_path: Path, freezer: FrozenDateTimeFactory
) -> str:
    """Set up a real Local Calendar named Family stored under tmp_path."""
    freezer.move_to(NOW)
    await hass.config.async_set_time_zone(TIME_ZONE)
    hass.config.config_dir = str(tmp_path)
    (tmp_path / ".storage").mkdir()
    entry = MockConfigEntry(
        domain="local_calendar",
        data={"calendar_name": "Family", "storage_key": f"test_{uuid.uuid4().hex}"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(CALENDAR_ENTITY_ID) is not None
    return CALENDAR_ENTITY_ID


@pytest.fixture
async def integration(hass: HomeAssistant, local_calendar: str) -> MockConfigEntry:
    """Set up the Calendar Actions config entry next to the Local Calendar."""
    entry = MockConfigEntry(domain=DOMAIN, title="Calendar Actions", data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def call(
    hass: HomeAssistant,
    service: str,
    context: Context | None = None,
    **data: Any,
) -> ServiceResponse:
    """Call a Calendar Actions service on the Family calendar."""
    return await hass.services.async_call(
        DOMAIN,
        service,
        {"entity_id": CALENDAR_ENTITY_ID, **data},
        blocking=True,
        context=context,
        return_response=service == "list_events",
    )


async def list_events(
    hass: HomeAssistant,
    start: str = "2026-10-01T00:00:00+02:00",
    end: str = "2027-01-01T00:00:00+01:00",
) -> list[dict[str, Any]]:
    """Return list_events output for a range."""
    response = await call(hass, "list_events", start=start, end=end)
    assert response is not None
    return response["events"]


async def create_weekly_series(hass: HomeAssistant, count: int = 4) -> str:
    """Create a weekly Monday 19:00 series that crosses the DST change; return uid."""
    await call(
        hass,
        "create_event",
        summary="Swimming",
        dtstart="2026-10-19T19:00:00+02:00",
        dtend="2026-10-19T20:00:00+02:00",
        rrule=f"FREQ=WEEKLY;COUNT={count}",
        location="Pool",
    )
    events = await list_events(hass)
    assert len(events) == count
    return events[0]["uid"]
