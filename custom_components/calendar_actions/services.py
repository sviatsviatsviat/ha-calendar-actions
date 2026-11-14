"""Calendar Actions services.

Each service calls the calendar entity in-process, the same way the calendar
WebSocket commands (`calendar/event/create|update|delete`) do. Events are
validated with the calendar component's own WebSocket event schema.
"""

from __future__ import annotations

import asyncio
import datetime
from collections import defaultdict
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any

import probatio
from homeassistant.auth.permissions.const import POLICY_CONTROL, POLICY_READ
from homeassistant.components.calendar import (
    WEBSOCKET_EVENT_SCHEMA,
    CalendarEntity,
    CalendarEvent,
)
from homeassistant.components.calendar.const import (
    DATA_COMPONENT,
    EVENT_DESCRIPTION,
    EVENT_END,
    EVENT_LOCATION,
    EVENT_RECURRENCE_ID,
    EVENT_RECURRENCE_RANGE,
    EVENT_RRULE,
    EVENT_START,
    EVENT_SUMMARY,
    EVENT_UID,
    CalendarEntityFeature,
)
from homeassistant.components.calendar.const import (
    DOMAIN as CALENDAR_DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import (
    ServiceValidationError,
    Unauthorized,
    UnknownUser,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .const import (
    ATTR_DURATION,
    ATTR_END,
    ATTR_START,
    DOMAIN,
    EVENT_SEARCH_LOOKAHEAD,
    EVENT_SEARCH_LOOKBACK,
    LIST_EVENT_FIELDS,
    RECURRENCE_RANGE_THIS_AND_FUTURE,
    SERVICE_CREATE_EVENT,
    SERVICE_DELETE_EVENT,
    SERVICE_LIST_EVENTS,
    SERVICE_UPDATE_EVENT,
)

_LOCKS: HassKey[defaultdict[str, asyncio.Lock]] = HassKey(f"{DOMAIN}_locks")

EVENT_FIELDS = (
    EVENT_SUMMARY,
    EVENT_START,
    EVENT_END,
    EVENT_RRULE,
    EVENT_DESCRIPTION,
    EVENT_LOCATION,
)


def _empty_as_none(value: Any) -> Any:
    """Treat an empty string as an omitted value."""
    return None if value == "" else value


_ENTITY_FIELD = {probatio.Required(ATTR_ENTITY_ID): cv.entity_domain(CALENDAR_DOMAIN)}
_TARGET_FIELDS = {
    probatio.Required(EVENT_UID): cv.string,
    probatio.Optional(EVENT_RECURRENCE_ID): probatio.All(
        _empty_as_none, probatio.Any(None, cv.string)
    ),
    probatio.Optional(EVENT_RECURRENCE_RANGE): probatio.All(
        _empty_as_none, probatio.Any(None, RECURRENCE_RANGE_THIS_AND_FUTURE)
    ),
}

# Event values are only coerced to strings here; WEBSOCKET_EVENT_SCHEMA does the
# real parsing inside the handler so its errors become ServiceValidationError.
CREATE_EVENT_SCHEMA = probatio.Schema(
    {
        **_ENTITY_FIELD,
        probatio.Required(EVENT_SUMMARY): cv.string,
        probatio.Required(EVENT_START): cv.string,
        probatio.Required(EVENT_END): cv.string,
        probatio.Optional(EVENT_RRULE): probatio.All(
            _empty_as_none, probatio.Any(None, cv.string)
        ),
        probatio.Optional(EVENT_DESCRIPTION): cv.string,
        probatio.Optional(EVENT_LOCATION): cv.string,
    }
)

UPDATE_EVENT_SCHEMA = probatio.Schema(
    {
        **_ENTITY_FIELD,
        **_TARGET_FIELDS,
        probatio.Optional(EVENT_SUMMARY): cv.string,
        probatio.Optional(EVENT_START): cv.string,
        probatio.Optional(EVENT_END): cv.string,
        probatio.Optional(EVENT_RRULE): probatio.All(
            _empty_as_none, probatio.Any(None, cv.string)
        ),
        probatio.Optional(EVENT_DESCRIPTION): cv.string,
        probatio.Optional(EVENT_LOCATION): cv.string,
    }
)

DELETE_EVENT_SCHEMA = probatio.Schema({**_ENTITY_FIELD, **_TARGET_FIELDS})

LIST_EVENTS_SCHEMA = probatio.All(
    probatio.Schema(
        {
            **_ENTITY_FIELD,
            probatio.Optional(ATTR_START): cv.datetime,
            probatio.Exclusive(ATTR_END, "end"): cv.datetime,
            probatio.Exclusive(ATTR_DURATION, "end"): probatio.All(
                cv.time_period, cv.positive_timedelta
            ),
        }
    ),
    probatio.AtLeastOne(ATTR_END, ATTR_DURATION),
)


async def _check_user(call: ServiceCall, entity_id: str, permission: str) -> None:
    """Raise when the calling user may not use the calendar entity."""
    if not (user_id := call.context.user_id):
        return
    user = await call.hass.auth.async_get_user(user_id)
    if user is None:
        raise UnknownUser(context=call.context, permission=permission)
    if not user.permissions.check_entity(entity_id, permission):
        raise Unauthorized(
            context=call.context,
            user_id=user_id,
            entity_id=entity_id,
            permission=permission,
        )


async def _get_entity(
    call: ServiceCall,
    permission: str,
    feature: CalendarEntityFeature | None,
) -> CalendarEntity:
    """Return the target calendar entity after permission and feature checks."""
    entity_id: str = call.data[ATTR_ENTITY_ID]
    await _check_user(call, entity_id, permission)

    component = call.hass.data.get(DATA_COMPONENT)
    entity = component.get_entity(entity_id) if component else None
    if entity is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entity_not_found",
            translation_placeholders={"entity_id": entity_id},
        )
    if not entity.available:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entity_unavailable",
            translation_placeholders={"entity_id": entity_id},
        )
    if feature is not None and not (entity.supported_features or 0) & feature:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="feature_not_supported",
            translation_placeholders={
                "entity_id": entity_id,
                "feature": feature.name.lower(),
            },
        )
    return entity


def _validate_event(data: dict[str, Any]) -> dict[str, Any]:
    """Validate an event with the calendar WebSocket schema."""
    try:
        return WEBSOCKET_EVENT_SCHEMA(data)
    # HA's rrule validator raises ValueError/TypeError for some malformed
    # rules (e.g. a part without "="), not only probatio.Invalid.
    except (probatio.Invalid, ValueError, TypeError) as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_event",
            translation_placeholders={"error": str(err)},
        ) from err


async def _call_backend(coro: Awaitable[None]) -> None:
    """Await a calendar entity mutation, mapping input errors to validation."""
    try:
        await coro
    # Backends (e.g. local_calendar) raise these for input they reject.
    # HomeAssistantError from the backend propagates unchanged.
    except (probatio.Invalid, ValueError) as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="backend_rejected",
            translation_placeholders={"error": str(err)},
        ) from err


def _check_target(data: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return recurrence_id and recurrence_range, rejecting a range alone."""
    recurrence_id = data.get(EVENT_RECURRENCE_ID)
    recurrence_range = data.get(EVENT_RECURRENCE_RANGE)
    if recurrence_range and not recurrence_id:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="range_requires_recurrence_id",
        )
    return recurrence_id, recurrence_range


async def _async_create_event(call: ServiceCall) -> None:
    """Create an event, optionally recurring."""
    entity = await _get_entity(call, POLICY_CONTROL, CalendarEntityFeature.CREATE_EVENT)
    event = _validate_event(
        _normalize_times(
            {
                key: value
                for key, value in call.data.items()
                if key in EVENT_FIELDS and value is not None
            }
        )
    )
    entity.async_set_context(call.context)
    await _call_backend(entity.async_create_event(**event))


async def _async_delete_event(call: ServiceCall) -> None:
    """Delete an event, a single instance, or an instance and the following."""
    entity = await _get_entity(call, POLICY_CONTROL, CalendarEntityFeature.DELETE_EVENT)
    recurrence_id, recurrence_range = _check_target(call.data)
    entity.async_set_context(call.context)
    await _call_backend(
        entity.async_delete_event(
            call.data[EVENT_UID],
            recurrence_id=recurrence_id,
            recurrence_range=recurrence_range,
        )
    )


def _event_to_response(event: CalendarEvent) -> dict[str, Any]:
    """Return the list_events representation of an event."""
    result: dict[str, Any] = {}
    for name in LIST_EVENT_FIELDS:
        value = getattr(event, name)
        if isinstance(value, datetime.datetime):
            value = dt_util.as_local(value).isoformat()
        elif isinstance(value, datetime.date):
            value = value.isoformat()
        if value is not None:
            result[name] = value
    return result


async def _async_list_events(call: ServiceCall) -> ServiceResponse:
    """List events with the identifiers needed by update/delete."""
    entity = await _get_entity(call, POLICY_READ, None)
    start = dt_util.as_local(call.data.get(ATTR_START) or dt_util.now())
    if ATTR_DURATION in call.data:
        end = start + call.data[ATTR_DURATION]
    else:
        end = dt_util.as_local(call.data[ATTR_END])
    if end <= start:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_range",
        )
    events = await entity.async_get_events(call.hass, start, end)
    return {"events": [_event_to_response(event) for event in events]}


async def _event_instances(
    hass: HomeAssistant, entity: CalendarEntity, uid: str
) -> list[CalendarEvent]:
    """Return the instances of an event in the search window, earliest first."""
    now = dt_util.now()
    events = await entity.async_get_events(
        hass, now - EVENT_SEARCH_LOOKBACK, now + EVENT_SEARCH_LOOKAHEAD
    )
    return sorted(
        (event for event in events if event.uid == uid),
        key=lambda event: event.start_datetime_local,
    )


def _is_changed_instance(event: CalendarEvent) -> bool:
    """Return True for an individually changed (detached) instance of a series.

    Expanded instances carry the series rule; a detached instance is stored as
    its own event with a recurrence_id and no rule.
    """
    return bool(event.recurrence_id) and not event.rrule


def _event_not_found(uid: str, recurrence_id: str | None) -> ServiceValidationError:
    return ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="event_not_found",
        translation_placeholders={
            "uid": uid,
            "recurrence_id": recurrence_id or "-",
        },
    )


async def _find_current_event(
    hass: HomeAssistant,
    entity: CalendarEntity,
    uid: str,
    recurrence_id: str | None,
    recurrence_range: str | None,
) -> CalendarEvent:
    """Find the event or instance an update applies to, refusing unsafe edits.

    The calendar entity API does not expose a series' original start, and a
    calendar applies a whole-series edit to the series start it is given (and,
    for Local Calendar, drops changed instances). So a recurring series is only
    edited from a known instance: alone, or with THISANDFUTURE.
    """
    instances = await _event_instances(hass, entity, uid)
    if not instances:
        raise _event_not_found(uid, recurrence_id)

    if recurrence_id is None:
        if any(event.rrule or event.recurrence_id for event in instances):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="series_update_requires_instance",
                translation_placeholders={"uid": uid},
            )
        return instances[0]

    target = next(
        (event for event in instances if event.recurrence_id == recurrence_id), None
    )
    if target is None:
        raise _event_not_found(uid, recurrence_id)

    if (
        recurrence_range
        and target is instances[0]
        and any(_is_changed_instance(event) for event in instances)
    ):
        # From what may be the series start, THISANDFUTURE is a whole-series
        # edit, which would drop the individually changed instances.
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="series_has_changed_instances",
            translation_placeholders={"uid": uid},
        )
    return target


def _normalize_times(data: dict[str, Any]) -> dict[str, Any]:
    """Parse dtstart/dtend and move aware datetimes to the local time zone.

    WEBSOCKET_EVENT_SCHEMA requires both values to share one tzinfo object, so
    offsets such as +01:00 and +02:00 (a DST change) or a mix with the
    current event's zone would otherwise be rejected.
    """
    result = dict(data)
    for key in (EVENT_START, EVENT_END):
        if (value := result.get(key)) is None:
            continue
        try:
            parsed = probatio.Any(cv.date, cv.datetime)(value)
        except probatio.Invalid as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_event",
                translation_placeholders={"error": f"{key}: {err}"},
            ) from err
        if isinstance(parsed, datetime.datetime) and parsed.tzinfo is not None:
            parsed = dt_util.as_local(parsed)
        result[key] = parsed
    return result


def _merge_times(current: CalendarEvent, patch: dict[str, Any]) -> tuple[Any, Any]:
    """Return start and end for the update, keeping the duration when one is set."""
    new_start = patch.get(EVENT_START)
    new_end = patch.get(EVENT_END)
    if new_start is not None and new_end is not None:
        return new_start, new_end
    if new_start is None and new_end is None:
        return current.start, current.end
    if new_end is not None:
        return current.start, new_end

    if isinstance(new_start, datetime.datetime) != isinstance(
        current.start, datetime.datetime
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="dtend_required",
        )
    return new_start, new_start + (current.end - current.start)


async def _async_update_event(call: ServiceCall) -> None:
    """Update an event by merging the given fields into the current event."""
    entity = await _get_entity(call, POLICY_CONTROL, CalendarEntityFeature.UPDATE_EVENT)
    recurrence_id, recurrence_range = _check_target(call.data)
    uid: str = call.data[EVENT_UID]
    patch = _normalize_times(
        {key: value for key, value in call.data.items() if key in EVENT_FIELDS}
    )
    if not patch:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="nothing_to_update",
        )

    new_rrule = patch.get(EVENT_RRULE)
    current = await _find_current_event(
        call.hass, entity, uid, recurrence_id, recurrence_range
    )
    start, end = _merge_times(current, patch)
    if isinstance(start, datetime.datetime) and start.tzinfo is not None:
        start = dt_util.as_local(start)
    if isinstance(end, datetime.datetime) and end.tzinfo is not None:
        end = dt_util.as_local(end)

    merged: dict[str, Any] = {
        EVENT_SUMMARY: patch.get(EVENT_SUMMARY, current.summary),
        EVENT_START: start,
        EVENT_END: end,
    }
    for key in (EVENT_DESCRIPTION, EVENT_LOCATION):
        value = patch.get(key, getattr(current, key))
        if value is not None:
            merged[key] = value
    # A single instance is not recurring; keep the rule for series edits only.
    if new_rrule is not None:
        merged[EVENT_RRULE] = new_rrule
    elif current.rrule and not (recurrence_id and not recurrence_range):
        merged[EVENT_RRULE] = current.rrule

    event = _validate_event(merged)
    entity.async_set_context(call.context)
    await _call_backend(
        entity.async_update_event(
            uid,
            event,
            recurrence_id=recurrence_id,
            recurrence_range=recurrence_range,
        )
    )


def _serialized(
    handler: Callable[[ServiceCall], Coroutine[Any, Any, None]],
) -> Callable[[ServiceCall], Coroutine[Any, Any, None]]:
    """Run a mutating handler under a per-calendar lock.

    update_event reads, merges and writes; without the lock a concurrent call
    could write between that read and write and have its change overwritten.
    """

    async def wrapper(call: ServiceCall) -> None:
        locks = call.hass.data.setdefault(_LOCKS, defaultdict(asyncio.Lock))
        async with locks[call.data[ATTR_ENTITY_ID]]:
            await handler(call)

    return wrapper


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Calendar Actions services."""
    handlers: tuple[tuple[str, Callable[..., Any], Any, SupportsResponse], ...] = (
        (
            SERVICE_CREATE_EVENT,
            _serialized(_async_create_event),
            CREATE_EVENT_SCHEMA,
            SupportsResponse.NONE,
        ),
        (
            SERVICE_UPDATE_EVENT,
            _serialized(_async_update_event),
            UPDATE_EVENT_SCHEMA,
            SupportsResponse.NONE,
        ),
        (
            SERVICE_DELETE_EVENT,
            _serialized(_async_delete_event),
            DELETE_EVENT_SCHEMA,
            SupportsResponse.NONE,
        ),
        (
            SERVICE_LIST_EVENTS,
            _async_list_events,
            LIST_EVENTS_SCHEMA,
            SupportsResponse.ONLY,
        ),
    )
    for service, handler, schema, supports_response in handlers:
        hass.services.async_register(
            DOMAIN, service, handler, schema=schema, supports_response=supports_response
        )
