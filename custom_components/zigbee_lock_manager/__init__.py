import logging
import asyncio
from homeassistant.core import HomeAssistant
from .const import (
    CONF_ACTIVITY_EVENT_COUNT,
    CONF_ENABLE_NOTIFICATIONS,
    CONF_ENABLE_PRESENCE_AUTOMATION,
    DEFAULT_ACTIVITY_EVENT_COUNT,
    DEFAULT_ENABLE_NOTIFICATIONS,
    DEFAULT_ENABLE_PRESENCE_AUTOMATION,
    LOCK_PROFILE_GENERIC,
)
from .zha_manager import (
    create_helpers_and_automations,
    remove_helpers_and_automations,
    link_helpers_to_device,
    create_dashboard_yaml  # Import the dashboard creation function
)
from homeassistant.helpers import device_registry as dr

_LOGGER = logging.getLogger(__name__)


def _entry_value(entry, key, default=None):
    """Return option value when present, otherwise fall back to entry data."""
    if key in entry.options:
        return entry.options.get(key)
    return entry.data.get(key, default)


async def _async_options_updated(hass: HomeAssistant, entry):
    """Reload entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_setup_entry(hass, entry):
    """Set up Zigbee Lock Manager from a config entry."""
    slot_count = _entry_value(entry, "slot_count")
    lock_name = entry.data.get("lock_name")
    lock_profile = _entry_value(entry, "lock_profile", LOCK_PROFILE_GENERIC)
    enable_notifications = _entry_value(
        entry, CONF_ENABLE_NOTIFICATIONS, DEFAULT_ENABLE_NOTIFICATIONS
    )
    enable_presence_automation = _entry_value(
        entry,
        CONF_ENABLE_PRESENCE_AUTOMATION,
        DEFAULT_ENABLE_PRESENCE_AUTOMATION,
    )
    activity_event_count = _entry_value(
        entry, CONF_ACTIVITY_EVENT_COUNT, DEFAULT_ACTIVITY_EVENT_COUNT
    )

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    # Step 1: Create the YAML-based helpers and automations
    await create_helpers_and_automations(
        hass,
        slot_count,
        lock_name,
        entry,
        lock_profile=lock_profile,
        enable_notifications=enable_notifications,
        enable_presence_automation=enable_presence_automation,
        activity_event_count=activity_event_count,
    )

    # Step 2: Reload automations and input helpers
    await hass.services.async_call("automation", "reload")
    await hass.services.async_call("input_boolean", "reload")
    await hass.services.async_call("input_text", "reload")
    await hass.services.async_call("input_button", "reload")

    # Step 3: Introduce a small delay to ensure entities are fully loaded
    await asyncio.sleep(2)  # Adjust the sleep duration if necessary

    # Step 4: Register a device for the lock manager
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(entry.domain, lock_name)},
        manufacturer="YourManufacturer",
        name=f"Zigbee Lock Manager ({lock_name})",
        model="Zigbee Lock",
        sw_version="1.0",
    )

    # Step 5: Link YAML-created helpers to the device
    for slot in range(1, slot_count + 1):
        await link_helpers_to_device(hass, entry, lock_name, slot, device)

    # Step 6: Create the dashboard YAML file
    await create_dashboard_yaml(
        hass,
        slot_count,
        lock_name,
        lock_profile=lock_profile,
        enable_notifications=enable_notifications,
        enable_presence_automation=enable_presence_automation,
        activity_event_count=activity_event_count,
    )

    _LOGGER.info("Zigbee Lock Manager setup complete")
    return True

async def async_unload_entry(hass: HomeAssistant, entry):
    """Unload Zigbee Lock Manager and clean up."""

    _LOGGER.debug("Unloading Zigbee Lock Manager.")

    # Remove helpers and automations
    await remove_helpers_and_automations(
        hass,
        entry.data.get("lock_name"),
        _entry_value(entry, "slot_count"),
    )

    _LOGGER.info("Zigbee Lock Manager unloaded.")
    return True
