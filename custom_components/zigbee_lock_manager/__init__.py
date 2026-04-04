import logging
import asyncio
import voluptuous as vol
from homeassistant.core import HomeAssistant
from .const import (
    CONF_ACTIVITY_EVENT_COUNT,
    CONF_BATTERY_LOW_THRESHOLD,
    CONF_ENABLE_ID_LOCK_ADVANCED_CONTROLS,
    CONF_ENABLE_NOTIFICATIONS,
    CONF_ENABLE_PRESENCE_AUTOMATION,
    DEFAULT_ACTIVITY_EVENT_COUNT,
    DEFAULT_BATTERY_LOW_THRESHOLD,
    DEFAULT_ENABLE_ID_LOCK_ADVANCED_CONTROLS,
    DEFAULT_ENABLE_NOTIFICATIONS,
    DEFAULT_ENABLE_PRESENCE_AUTOMATION,
    DOMAIN,
    LOCK_PROFILE_GENERIC,
)
from .zha_manager import (
    create_helpers_and_automations,
    remove_helpers_and_automations,
    link_all_generated_helpers_to_device,
    create_dashboard_yaml  # Import the dashboard creation function
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)

SERVICE_ID_LOCK_202_MANUAL_SYNC_GUIDE = "id_lock_202_manual_sync_guide"


def _register_services(hass: HomeAssistant) -> None:
    """Register domain services once."""
    if hass.services.has_service(DOMAIN, SERVICE_ID_LOCK_202_MANUAL_SYNC_GUIDE):
        return

    async def _handle_manual_sync_guide(call):
        lock_entity = call.data.get("lock_entity", "(selected lock)")
        title = f"ID Lock 202 manual sync guide: {lock_entity}"
        message = (
            "1) Open the door.\n"
            "2) Hold key button until panel is active.\n"
            "3) Enter [Master PIN], then *.\n"
            "4) Enter 9, then *.\n"
            "5) Enter 1 to start manual sync."
        )

        if hass.services.has_service("persistent_notification", "create"):
            await hass.services.async_call(
                "persistent_notification",
                "create",
                {"title": title, "message": message},
            )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ID_LOCK_202_MANUAL_SYNC_GUIDE,
        _handle_manual_sync_guide,
        schema=vol.Schema({vol.Optional("lock_entity"): str}),
    )


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
    _register_services(hass)

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
    enable_id_lock_advanced_controls = _entry_value(
        entry,
        CONF_ENABLE_ID_LOCK_ADVANCED_CONTROLS,
        DEFAULT_ENABLE_ID_LOCK_ADVANCED_CONTROLS,
    )
    battery_low_threshold = _entry_value(
        entry,
        CONF_BATTERY_LOW_THRESHOLD,
        DEFAULT_BATTERY_LOW_THRESHOLD,
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
        enable_id_lock_advanced_controls=enable_id_lock_advanced_controls,
        battery_low_threshold=battery_low_threshold,
        activity_event_count=activity_event_count,
    )

    # Step 2: Reload automations and input helpers when services are available.
    services_to_reload = (
        ("automation", "reload"),
        ("input_boolean", "reload"),
        ("input_text", "reload"),
        ("input_button", "reload"),
        ("input_number", "reload"),
        ("input_select", "reload"),
    )
    for domain, service in services_to_reload:
        if hass.services.has_service(domain, service):
            await hass.services.async_call(domain, service)
        else:
            _LOGGER.warning("%s.%s service not available at this time", domain, service)

    # Step 3: Introduce a small delay to ensure entities are fully loaded
    await asyncio.sleep(2)  # Adjust the sleep duration if necessary

    # Step 4: Resolve target device for helper linking.
    # Prefer the real lock device so users see lock controls and helpers together.
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    lock_entity_id = f"lock.{lock_name}"
    lock_entity_entry = entity_registry.async_get(lock_entity_id)
    if lock_entity_entry and lock_entity_entry.device_id:
        device = device_registry.async_get(lock_entity_entry.device_id)
    else:
        device = None

    stale_manager_device = device_registry.async_get_device(
        identifiers={(entry.domain, lock_name)}
    )

    if device is None:
        if stale_manager_device is not None:
            device = stale_manager_device
        else:
            device = device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers={(entry.domain, lock_name)},
                manufacturer="YourManufacturer",
                name=f"Zigbee Lock Manager ({lock_name})",
                model="Zigbee Lock",
                sw_version="1.0",
            )
    else:
        # A real lock device exists. Remove stale manager placeholder device to
        # avoid presenting an empty device page in the UI.
        if stale_manager_device is not None:
            device_registry.async_remove_device(stale_manager_device.id)

    # Step 5: Link all YAML-created helpers to the target device.
    await link_all_generated_helpers_to_device(hass, lock_name, device.id)

    # Step 6: Create the dashboard YAML file
    await create_dashboard_yaml(
        hass,
        slot_count,
        lock_name,
        lock_profile=lock_profile,
        enable_notifications=enable_notifications,
        enable_presence_automation=enable_presence_automation,
        enable_id_lock_advanced_controls=enable_id_lock_advanced_controls,
        battery_low_threshold=battery_low_threshold,
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
