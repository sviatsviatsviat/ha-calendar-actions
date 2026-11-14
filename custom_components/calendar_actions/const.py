"""Constants for the Calendar Actions integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "calendar_actions"
NAME: Final = "Calendar Actions"

SERVICE_CREATE_EVENT: Final = "create_event"
SERVICE_UPDATE_EVENT: Final = "update_event"
SERVICE_DELETE_EVENT: Final = "delete_event"
SERVICE_LIST_EVENTS: Final = "list_events"

ATTR_START: Final = "start"
ATTR_END: Final = "end"
ATTR_DURATION: Final = "duration"

RECURRENCE_RANGE_THIS_AND_FUTURE: Final = "THISANDFUTURE"

# Fields returned per event by list_events.
LIST_EVENT_FIELDS: Final = (
    "uid",
    "recurrence_id",
    "rrule",
    "summary",
    "start",
    "end",
    "description",
    "location",
)

# update_event looks up the current event before merging a partial patch.
# An instance is searched near its recurrence_id first, then in the wide window.
INSTANCE_SEARCH_MARGIN: Final = timedelta(days=2)
EVENT_SEARCH_LOOKBACK: Final = timedelta(days=5 * 366)
EVENT_SEARCH_LOOKAHEAD: Final = timedelta(days=5 * 366)
