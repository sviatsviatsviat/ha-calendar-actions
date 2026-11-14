"""Tests for rejected inputs and per-call checks."""

from typing import Any

import probatio
import pytest
from homeassistant.auth.models import User
from homeassistant.components.calendar.const import DATA_COMPONENT
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import (
    ServiceValidationError,
    Unauthorized,
    UnknownUser,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import CALENDAR_ENTITY_ID, call, create_weekly_series, list_events

EVENT = {
    "summary": "Test",
    "dtstart": "2026-10-20T09:00:00+02:00",
    "dtend": "2026-10-20T10:00:00+02:00",
}


@pytest.mark.parametrize(
    "overrides",
    [
        {"rrule": "FREQ=HOURLY"},
        {"rrule": "INTERVAL=2;BYDAY=MO"},
        {"rrule": "WEEKLY"},
        {"rrule": "RRULE:FREQ=WEEKLY"},
        {"dtend": "2026-10-20T08:00:00+02:00"},
        {"dtstart": "not a date"},
        {"dtend": "2026-10-21"},
    ],
    ids=[
        "hourly",
        "no_freq",
        "no_equals",
        "rrule_prefix",
        "end_before_start",
        "bad_date",
        "mixed_types",
    ],
)
async def test_invalid_event_rejected(
    hass: HomeAssistant, integration: MockConfigEntry, overrides: dict[str, Any]
) -> None:
    """Invalid events raise ServiceValidationError and create nothing."""
    with pytest.raises(ServiceValidationError):
        await call(hass, "create_event", **{**EVENT, **overrides})
    assert await list_events(hass) == []


async def test_unknown_entity(
    hass: HomeAssistant, integration: MockConfigEntry
) -> None:
    """An unknown calendar is a validation error."""
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            "calendar_actions",
            "create_event",
            {"entity_id": "calendar.missing", **EVENT},
            blocking=True,
        )
    assert err.value.translation_key == "entity_not_found"


async def test_non_calendar_entity_rejected(
    hass: HomeAssistant, integration: MockConfigEntry
) -> None:
    """The entity must be in the calendar domain."""
    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            "calendar_actions",
            "create_event",
            {"entity_id": "light.kitchen", **EVENT},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("service", "data"),
    [
        ("create_event", EVENT),
        ("update_event", {"uid": "x", "summary": "y"}),
        ("delete_event", {"uid": "x"}),
    ],
)
async def test_feature_not_supported(
    hass: HomeAssistant,
    integration: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    service: str,
    data: dict[str, Any],
) -> None:
    """A calendar without the needed feature is rejected."""
    entity = hass.data[DATA_COMPONENT].get_entity(CALENDAR_ENTITY_ID)
    monkeypatch.setattr(entity, "_attr_supported_features", 0)
    with pytest.raises(ServiceValidationError) as err:
        await call(hass, service, **data)
    assert err.value.translation_key == "feature_not_supported"


async def test_unavailable_calendar(
    hass: HomeAssistant,
    integration: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unavailable calendar is rejected."""
    entity = hass.data[DATA_COMPONENT].get_entity(CALENDAR_ENTITY_ID)
    monkeypatch.setattr(entity, "_attr_available", False)
    with pytest.raises(ServiceValidationError) as err:
        await call(hass, "create_event", **EVENT)
    assert err.value.translation_key == "entity_unavailable"


async def test_read_only_user_cannot_mutate_but_can_list(
    hass: HomeAssistant,
    integration: MockConfigEntry,
    hass_read_only_user: User,
) -> None:
    """Mutations need control permission; listing needs read permission."""
    context = Context(user_id=hass_read_only_user.id)
    with pytest.raises(Unauthorized):
        await call(hass, "create_event", context=context, **EVENT)

    await create_weekly_series(hass, count=1)
    response = await call(
        hass,
        "list_events",
        context=context,
        start="2026-10-01T00:00:00+02:00",
        end="2026-11-01T00:00:00+01:00",
    )
    assert response is not None
    assert len(response["events"]) == 1


async def test_unknown_user(hass: HomeAssistant, integration: MockConfigEntry) -> None:
    """A context with an unknown user is rejected."""
    with pytest.raises(UnknownUser):
        await call(
            hass, "create_event", context=Context(user_id="no-such-user"), **EVENT
        )


async def test_list_end_before_start(
    hass: HomeAssistant, integration: MockConfigEntry
) -> None:
    """list_events rejects an empty range."""
    with pytest.raises(ServiceValidationError) as err:
        await list_events(
            hass, start="2026-10-10T00:00:00+02:00", end="2026-10-01T00:00:00+02:00"
        )
    assert err.value.translation_key == "invalid_range"


async def test_invalid_recurrence_range(
    hass: HomeAssistant, integration: MockConfigEntry
) -> None:
    """Only THISANDFUTURE is accepted as recurrence_range."""
    with pytest.raises(probatio.Invalid):
        await call(
            hass, "delete_event", uid="x", recurrence_id="1", recurrence_range="ALL"
        )
