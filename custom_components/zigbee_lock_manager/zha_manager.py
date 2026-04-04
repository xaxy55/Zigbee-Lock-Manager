import os
import jinja2
import aiofiles
import logging
import shutil
import asyncio
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import device_registry as dr
from .const import (
    DEFAULT_ACTIVITY_EVENT_COUNT,
    DOMAIN,
    LOCK_PROFILE_ID_LOCK_202_MULTI,
)

_LOGGER = logging.getLogger(__name__)

PACKAGE_DIR = "packages/zigbee_lock_manager"
DASHBOARD_FILE = "zigbee_lock_manager_dashboard"  # Output file for the dashboard YAML


def profile_render_settings(lock_profile: str) -> dict[str, str | int]:
    """Return rendering settings for a lock profile."""
    is_id_lock_202 = lock_profile == LOCK_PROFILE_ID_LOCK_202_MULTI
    return {
        "code_label": "Lock PIN" if is_id_lock_202 else "Lock Code",
        "code_max": 10,
        "code_validation_regex": "^[0-9]{4,10}$" if is_id_lock_202 else "^.{1,10}$",
        "invalid_code_message": (
            "Code slot {{ slot }} was not updated. Enter 4-10 digits only (ID Lock 202 Multi)."
            if is_id_lock_202
            else "Code slot {{ slot }} was not updated. Enter 1-10 characters."
        ),
    }


def lock_slot_file_prefix(lock_name: str) -> str:
    """Return generated slot filename prefix for a lock."""
    return f"{lock_name.replace('.', '_')}_slot_"


def _safe_path_within(base: str, filename: str) -> str:
    """Return ``os.path.join(base, filename)`` and raise if the result
    escapes *base* (path-traversal guard – OWASP A01)."""
    full_path = os.path.realpath(os.path.join(base, filename))
    base_real = os.path.realpath(base)
    # Ensure the resolved path starts with the base directory.
    if not (full_path == base_real or full_path.startswith(base_real + os.sep)):
        raise ValueError(
            f"Path traversal detected: {full_path!r} is outside {base_real!r}"
        )
    return full_path

async def load_template(template_name):
    """Helper function to load the template files."""
    template_path = os.path.join(os.path.dirname(__file__), template_name)
    async with aiofiles.open(template_path, 'r') as template_file:
        return await template_file.read()

# Register a device for the integration
async def create_integration_device(hass, config_entry, lock_name):
    device_registry = dr.async_get(hass)
    # Register the device
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, lock_name)},
        manufacturer="Your Manufacturer",
        model="Lock Model",
        name=f"{lock_name} Zigbee Lock Manager",
        sw_version="1.0"
    )

async def create_helpers_and_automations(
    hass: HomeAssistant,
    slot_count: int,
    lock_name: str,
    config_entry,
    lock_profile: str = "generic",
    enable_notifications: bool = False,
    enable_presence_automation: bool = False,
    activity_event_count: int = DEFAULT_ACTIVITY_EVENT_COUNT,
):
    """Create helpers and automations."""
    package_path = hass.config.path(PACKAGE_DIR)
    
    # Create the device in the registry
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, lock_name)},
        manufacturer="YourManufacturer",
        name=f"Zigbee Lock Manager ({lock_name})",
        model="Zigbee Lock",
        sw_version="1.0",
    )

    # Ensure the directory exists
    if not os.path.exists(package_path):
        os.makedirs(package_path)

    # Load the template content
    template_content = await load_template("zha_manager_template.yaml")
    template = jinja2.Template(template_content)

    render_settings = profile_render_settings(lock_profile)

    entity_registry = er.async_get(hass)

    # Remove previously generated slot YAML files for this lock so option
    # changes (for example, lower slot_count) don't leave stale automations.
    lock_file_prefix = lock_slot_file_prefix(lock_name)
    for filename in os.listdir(package_path):
        if filename.startswith(lock_file_prefix) and filename.endswith(".yaml"):
            stale_file_path = _safe_path_within(package_path, filename)
            os.remove(stale_file_path)
            _LOGGER.debug("Removed stale slot YAML: %s", stale_file_path)

    # Generate a separate YAML file for each slot
    for slot in range(1, slot_count + 1):
        yaml_file_path = _safe_path_within(
            package_path,
            f"{lock_name.replace('.', '_')}_slot_{slot}.yaml",
        )

        # Replace the placeholders in the template for the current slot
        final_yaml_content = template.render(
            lock_name=lock_name,
            slot=slot,
            slot_count=slot_count,
            code_label=render_settings["code_label"],
            code_max=render_settings["code_max"],
            code_validation_regex=render_settings["code_validation_regex"],
            invalid_code_message=render_settings["invalid_code_message"],
            enable_notifications=enable_notifications,
            enable_presence_automation=enable_presence_automation,
            activity_event_count=activity_event_count,
        )

        # Write the final YAML content to the corresponding slot file
        async with aiofiles.open(yaml_file_path, 'w') as yaml_file:
            await yaml_file.write(final_yaml_content)

        _LOGGER.info(f"Created helpers and automations for slot {slot} in {yaml_file_path}")

    # Step to reload automations and helpers, but only if services are available
    if hass.services.has_service("automation", "reload"):
        await hass.services.async_call("automation", "reload")
    else:
        _LOGGER.warning("automation.reload service not available at this time")

    if hass.services.has_service("input_boolean", "reload"):
        await hass.services.async_call("input_boolean", "reload")
    else:
        _LOGGER.warning("input_boolean.reload service not available at this time")

    if hass.services.has_service("input_text", "reload"):
        await hass.services.async_call("input_text", "reload")
    else:
        _LOGGER.warning("input_text.reload service not available at this time")

    if hass.services.has_service("input_button", "reload"):
        await hass.services.async_call("input_button", "reload")
    else:
        _LOGGER.warning("input_button.reload service not available at this time")

    # Wait for 2 seconds to ensure entities are registered
    await asyncio.sleep(1)


async def link_helpers_to_device(hass, config_entry, lock_name, slot, device):
    """Link YAML-created helpers to a device by updating their device_id in the entity registry."""
    entity_registry = er.async_get(hass)

    # Define the expected entity_id for the helpers from the YAML configuration
    entity_id_input_text_user = f"input_text.{lock_name}_lock_user_{slot}" 
    entity_id_input_text_code = f"input_text.{lock_name}_lock_code_{slot}"  
    entity_id_input_boolean_status = f"input_boolean.{lock_name}_lock_code_status_{slot}"
    entity_id_input_boolean_onetime = f"input_boolean.{lock_name}_lock_code_onetime_{slot}"
    entity_id_input_boolean_presence_aware = (
        f"input_boolean.{lock_name}_lock_code_presence_aware_{slot}"
    )
    entity_id_input_button_update = f"input_button.{lock_name}_lock_code_update_{slot}"
    entity_id_input_button_clear = f"input_button.{lock_name}_lock_code_clear_{slot}"

    # Create a list of expected entities
    entities = [
        {"entity_id": entity_id_input_text_user, "domain": "input_text"},
        {"entity_id": entity_id_input_text_code, "domain": "input_text"},
        {"entity_id": entity_id_input_boolean_status, "domain": "input_boolean"},
        {"entity_id": entity_id_input_boolean_onetime, "domain": "input_boolean"},
        {
            "entity_id": entity_id_input_boolean_presence_aware,
            "domain": "input_boolean",
        },
        {"entity_id": entity_id_input_button_update, "domain": "input_button"},
        {"entity_id": entity_id_input_button_clear, "domain": "input_button"},
    ]

    # Loop through each entity, check if it exists, and link it to the device
    for entity in entities:
        _LOGGER.debug(f"Looking for entity: {entity['entity_id']}")
        # Try to find the entity in the entity registry
        entity_entry = entity_registry.async_get(entity["entity_id"])

        if entity_entry:
            _LOGGER.info(f"Entity found: {entity['entity_id']} - linking to device {device.id}")
            # Entity exists, now update it to link to the device
            entity_registry.async_update_entity(
                entity_entry.entity_id,
                device_id=device.id,  # Link to the device
                config_entry_id=config_entry.entry_id  # Associate with the config entry
            )
            _LOGGER.info(f"Linked {entity['entity_id']} to device {device.id}")
        else:
            _LOGGER.warning(f"Entity {entity['entity_id']} not found in entity registry.")

# New function to create the dashboard YAML
async def create_dashboard_yaml(
    hass: HomeAssistant,
    slot_count: int,
    lock_name: str,
    lock_profile: str = "generic",
    enable_notifications: bool = False,
    enable_presence_automation: bool = False,
    activity_event_count: int = DEFAULT_ACTIVITY_EVENT_COUNT,
):
    """Generate a dashboard YAML file."""
    package_path = hass.config.path(PACKAGE_DIR)
    # Load the dashboard head and card templates
    dashboard_head = await load_template("zha_dashboard_head.yaml")
    dashboard_card_template = await load_template("zha_dashboard_card.yaml")
    dashboard_card = jinja2.Template(dashboard_card_template)

    dashboard_file_path = _safe_path_within(package_path, DASHBOARD_FILE)

    async with aiofiles.open(dashboard_file_path, 'w') as dashboard_file:
        # Replace {{ lock_name }} in dashboard head
        dashboard_head_final = jinja2.Template(dashboard_head).render(
            lock_name=lock_name,
            lock_profile=lock_profile,
            enable_notifications=enable_notifications,
            enable_presence_automation=enable_presence_automation,
            activity_event_count=activity_event_count,
        )

        # Write the dashboard head first
        await dashboard_file.write(dashboard_head_final)
        await dashboard_file.write("\n")

        # Process each slot's card
        for slot in range(1, slot_count + 1):
            card_content = dashboard_card.render(
                lock_name=lock_name,
                slot=slot,
                lock_profile=lock_profile,
            )
            await dashboard_file.write(card_content)
            await dashboard_file.write("\n")

    _LOGGER.info(f"Created dashboard YAML for {slot_count} slots at {dashboard_file_path}")

# Remove helpers and automations
async def remove_helpers_and_automations(hass, lock_name, slot_count):
    """Remove helpers and automations for lock manager."""
    entity_registry = er.async_get(hass)
    lock_prefixes = (
        f"input_text.{lock_name}_",
        f"input_boolean.{lock_name}_",
        f"input_button.{lock_name}_",
    )

    # Remove only entities generated for this lock instance.
    entities_to_remove = [
        entity for entity in entity_registry.entities.values()
        if any(entity.entity_id.startswith(prefix) for prefix in lock_prefixes)
    ]
    for entity in entities_to_remove:
        entity_registry.async_remove(entity.entity_id)

    # Remove only generated YAML for this lock and optional dashboard file.
    package_path = hass.config.path(PACKAGE_DIR)
    lock_file_prefix = lock_slot_file_prefix(lock_name)
    if os.path.isdir(package_path):
        for filename in os.listdir(package_path):
            if filename.startswith(lock_file_prefix) and filename.endswith(".yaml"):
                slot_file_path = _safe_path_within(package_path, filename)
                os.remove(slot_file_path)

        dashboard_file_path = _safe_path_within(package_path, DASHBOARD_FILE)
        if os.path.isfile(dashboard_file_path):
            os.remove(dashboard_file_path)

        if not os.listdir(package_path):
            await hass.async_add_executor_job(shutil.rmtree, package_path)

    _LOGGER.info("Zigbee Lock Manager helpers and automations removed.")
