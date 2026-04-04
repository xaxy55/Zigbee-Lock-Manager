import re
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
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
    LOCK_PROFILE_ID_LOCK_202_MULTI,
    LOCK_PROFILE_OPTIONS,
    ID_LOCK_202_MANUFACTURER_HINTS,
    ID_LOCK_202_MODEL_HINTS,
)
import logging

_LOGGER = logging.getLogger(__name__)

# Permitted characters for a lock object_id derived from a HA entity ID.
# HA restricts object IDs to lowercase letters, digits, underscores, and hyphens.
_SAFE_NAME_RE = re.compile(r'^[a-z0-9_\-]+$')


def infer_lock_profile(manufacturer: str | None, model: str | None) -> str:
    """Infer lock profile from manufacturer and model names."""
    manufacturer_l = (manufacturer or "").strip().lower()
    model_l = (model or "").strip().lower()

    if any(hint in manufacturer_l for hint in ID_LOCK_202_MANUFACTURER_HINTS):
        return LOCK_PROFILE_ID_LOCK_202_MULTI
    if any(hint in model_l for hint in ID_LOCK_202_MODEL_HINTS):
        return LOCK_PROFILE_ID_LOCK_202_MULTI

    return LOCK_PROFILE_GENERIC

class LockCodeFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the configuration flow for Zigbee Lock Manager."""

    VERSION = 1.0

    def _detect_profile_for_lock_entity(self, lock_entity_id: str) -> str:
        """Detect lock profile for a selected lock entity via registries."""
        entity_registry = er.async_get(self.hass)
        device_registry = dr.async_get(self.hass)

        entity_entry = entity_registry.async_get(lock_entity_id)
        if not entity_entry or not entity_entry.device_id:
            return LOCK_PROFILE_GENERIC

        device = device_registry.async_get(entity_entry.device_id)
        if not device:
            return LOCK_PROFILE_GENERIC

        return infer_lock_profile(device.manufacturer, device.model)

    @staticmethod
    def async_get_options_flow(config_entry):
        """Get the options flow handler."""
        return LockCodeOptionsFlowHandler(config_entry)

    async def _async_maybe_notify_id_lock_safety(self, lock_profile: str) -> None:
        """Send a one-time setup reminder for ID Lock 202 battery handling."""
        if lock_profile != LOCK_PROFILE_ID_LOCK_202_MULTI:
            return

        if self.hass.services.has_service("persistent_notification", "create"):
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "ID Lock 202 setup reminder",
                    "message": (
                        "When inserting or removing the Zigbee module, remove batteries first. "
                        "Operating on the module with batteries inserted can damage the module."
                    ),
                },
            )

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        # Fetch available lock entities (assume they are in the format lock.some_lock_name)
        lock_entities = [entity.entity_id for entity in self.hass.states.async_all("lock")]

        # Handle the case where no lock entities are available
        if not lock_entities:
            _LOGGER.warning("No locks found during config flow")
            return self.async_abort(reason="no_locks")

        if user_input is not None:
            # Extract only the part after "lock." from the lock entity ID
            full_lock_entity_id = user_input["lock_name"]
            lock_name = full_lock_entity_id.split("lock.")[1]

            # Validate that lock_name contains only safe characters before it is
            # used in file-system paths and YAML generation (prevents path traversal
            # and injection – OWASP A01 / A03).
            if not _SAFE_NAME_RE.match(lock_name):
                errors["base"] = "invalid_lock_name"
                _LOGGER.warning("Rejected unsafe lock name during config flow")
            else:
                if not user_input.get("lock_profile"):
                    user_input["lock_profile"] = self._detect_profile_for_lock_entity(
                        full_lock_entity_id
                    )

                # Store the processed lock_name instead of the full entity ID
                user_input["lock_name"] = lock_name

                await self._async_maybe_notify_id_lock_safety(
                    user_input.get("lock_profile", LOCK_PROFILE_GENERIC)
                )

                _LOGGER.debug("Config flow completed for lock: %s, slots: %s",
                              lock_name, user_input.get("slot_count"))

                # Automatically use the lock_name as the title for the integration entry
                return self.async_create_entry(title=f"Zigbee Lock Manager - {lock_name}", data=user_input)

        # Define the form schema.
        # slot_count is bounded to prevent DoS via mass file creation (OWASP A05).
        schema = vol.Schema({
            vol.Required("slot_count", default=1): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=100)
            ),
            vol.Required("lock_name", default=lock_entities[0]): vol.In(lock_entities),
            vol.Optional(
                "lock_profile",
                default=self._detect_profile_for_lock_entity(lock_entities[0]),
            ): vol.In(LOCK_PROFILE_OPTIONS),
            vol.Optional(
                CONF_ENABLE_NOTIFICATIONS,
                default=DEFAULT_ENABLE_NOTIFICATIONS,
            ): bool,
            vol.Optional(
                CONF_ENABLE_PRESENCE_AUTOMATION,
                default=DEFAULT_ENABLE_PRESENCE_AUTOMATION,
            ): bool,
            vol.Optional(
                CONF_ACTIVITY_EVENT_COUNT,
                default=DEFAULT_ACTIVITY_EVENT_COUNT,
            ): vol.All(vol.Coerce(int), vol.Range(min=3, max=10)),
            vol.Optional(
                CONF_ENABLE_ID_LOCK_ADVANCED_CONTROLS,
                default=DEFAULT_ENABLE_ID_LOCK_ADVANCED_CONTROLS,
            ): bool,
            vol.Optional(
                CONF_BATTERY_LOW_THRESHOLD,
                default=DEFAULT_BATTERY_LOW_THRESHOLD,
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=100)),
        })

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class LockCodeOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Zigbee Lock Manager options."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    def _detect_profile_for_lock_entity(self, lock_entity_id: str) -> str:
        """Detect lock profile for a selected lock entity via registries."""
        entity_registry = er.async_get(self.hass)
        device_registry = dr.async_get(self.hass)

        entity_entry = entity_registry.async_get(lock_entity_id)
        if not entity_entry or not entity_entry.device_id:
            return LOCK_PROFILE_GENERIC

        device = device_registry.async_get(entity_entry.device_id)
        if not device:
            return LOCK_PROFILE_GENERIC

        return infer_lock_profile(device.manufacturer, device.model)

    async def async_step_init(self, user_input=None):
        """Manage integration options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_slot_count = self.config_entry.options.get(
            "slot_count", self.config_entry.data.get("slot_count", 1)
        )
        current_lock_profile = self.config_entry.options.get(
            "lock_profile",
            self.config_entry.data.get(
                "lock_profile",
                self._detect_profile_for_lock_entity(
                    f"lock.{self.config_entry.data.get('lock_name', '')}"
                ),
            ),
        )
        current_enable_notifications = self.config_entry.options.get(
            CONF_ENABLE_NOTIFICATIONS,
            self.config_entry.data.get(
                CONF_ENABLE_NOTIFICATIONS, DEFAULT_ENABLE_NOTIFICATIONS
            ),
        )
        current_enable_presence_automation = self.config_entry.options.get(
            CONF_ENABLE_PRESENCE_AUTOMATION,
            self.config_entry.data.get(
                CONF_ENABLE_PRESENCE_AUTOMATION, DEFAULT_ENABLE_PRESENCE_AUTOMATION
            ),
        )
        current_activity_event_count = self.config_entry.options.get(
            CONF_ACTIVITY_EVENT_COUNT,
            self.config_entry.data.get(
                CONF_ACTIVITY_EVENT_COUNT, DEFAULT_ACTIVITY_EVENT_COUNT
            ),
        )
        current_enable_id_lock_advanced_controls = self.config_entry.options.get(
            CONF_ENABLE_ID_LOCK_ADVANCED_CONTROLS,
            self.config_entry.data.get(
                CONF_ENABLE_ID_LOCK_ADVANCED_CONTROLS,
                DEFAULT_ENABLE_ID_LOCK_ADVANCED_CONTROLS,
            ),
        )
        current_battery_low_threshold = self.config_entry.options.get(
            CONF_BATTERY_LOW_THRESHOLD,
            self.config_entry.data.get(
                CONF_BATTERY_LOW_THRESHOLD,
                DEFAULT_BATTERY_LOW_THRESHOLD,
            ),
        )

        schema = vol.Schema({
            vol.Required("slot_count", default=current_slot_count): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=100)
            ),
            vol.Optional("lock_profile", default=current_lock_profile): vol.In(
                LOCK_PROFILE_OPTIONS
            ),
            vol.Optional(
                CONF_ENABLE_NOTIFICATIONS,
                default=current_enable_notifications,
            ): bool,
            vol.Optional(
                CONF_ENABLE_PRESENCE_AUTOMATION,
                default=current_enable_presence_automation,
            ): bool,
            vol.Optional(
                CONF_ACTIVITY_EVENT_COUNT,
                default=current_activity_event_count,
            ): vol.All(vol.Coerce(int), vol.Range(min=3, max=10)),
            vol.Optional(
                CONF_ENABLE_ID_LOCK_ADVANCED_CONTROLS,
                default=current_enable_id_lock_advanced_controls,
            ): bool,
            vol.Optional(
                CONF_BATTERY_LOW_THRESHOLD,
                default=current_battery_low_threshold,
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=100)),
        })

        return self.async_show_form(step_id="init", data_schema=schema)
