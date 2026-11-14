"""Tests for the Calendar Actions config flow and setup."""

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.calendar_actions.const import DOMAIN


async def test_user_flow_creates_entry_and_registers_services(
    hass: HomeAssistant,
) -> None:
    """The user step confirms, creates the entry and the services exist."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Calendar Actions"
    assert result["data"] == {}

    for service in ("create_event", "update_event", "delete_event", "list_events"):
        assert hass.services.has_service(DOMAIN, service)


async def test_second_entry_is_rejected(hass: HomeAssistant) -> None:
    """Only one Calendar Actions entry is allowed."""
    MockConfigEntry(domain=DOMAIN, data={}).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_entry_unloads(hass: HomeAssistant) -> None:
    """The entry sets up and unloads cleanly."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is config_entries.ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED
