"""Tests for delete_event."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import call, create_weekly_series, list_events


async def test_delete_whole_series(
    hass: HomeAssistant, integration: MockConfigEntry
) -> None:
    """Without recurrence_id the whole series is deleted."""
    uid = await create_weekly_series(hass)
    await call(hass, "delete_event", uid=uid)
    assert await list_events(hass) == []


async def test_delete_single_instance(
    hass: HomeAssistant, integration: MockConfigEntry
) -> None:
    """recurrence_id alone deletes only that instance."""
    uid = await create_weekly_series(hass)
    before = await list_events(hass)

    await call(hass, "delete_event", uid=uid, recurrence_id=before[1]["recurrence_id"])

    after = await list_events(hass)
    assert [e["start"] for e in after] == [before[i]["start"] for i in (0, 2, 3)]


async def test_delete_this_and_future(
    hass: HomeAssistant, integration: MockConfigEntry
) -> None:
    """THISANDFUTURE deletes the instance and all following ones."""
    uid = await create_weekly_series(hass)
    before = await list_events(hass)

    await call(
        hass,
        "delete_event",
        uid=uid,
        recurrence_id=before[2]["recurrence_id"],
        recurrence_range="THISANDFUTURE",
    )

    after = await list_events(hass)
    assert [e["start"] for e in after] == [before[0]["start"], before[1]["start"]]


async def test_range_requires_recurrence_id(
    hass: HomeAssistant, integration: MockConfigEntry
) -> None:
    """THISANDFUTURE without recurrence_id is rejected instead of deleting all."""
    uid = await create_weekly_series(hass)
    with pytest.raises(ServiceValidationError) as err:
        await call(hass, "delete_event", uid=uid, recurrence_range="THISANDFUTURE")
    assert err.value.translation_key == "range_requires_recurrence_id"
    assert len(await list_events(hass)) == 4


async def test_delete_unknown_uid_raises_backend_error(
    hass: HomeAssistant, integration: MockConfigEntry
) -> None:
    """The calendar's own error for an unknown uid propagates."""
    with pytest.raises(HomeAssistantError):
        await call(hass, "delete_event", uid="missing")
