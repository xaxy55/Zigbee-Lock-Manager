import re
from collections.abc import Mapping
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from .const import (
    CAP_SUPPORTS_BATTERY_PERCENTAGE,
    CAP_SUPPORTS_ID_LOCK_ADVANCED_CONTROLS,
    CONF_ACTIVITY_EVENT_COUNT,
    CONF_BATTERY_LOW_THRESHOLD,
    CONF_ENABLE_ID_LOCK_ADVANCED_CONTROLS,
    CONF_LOCK_CAPABILITIES,
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
_ID_LOCK_ADVANCED_PROBE_ATTRIBUTES = {
    "sound_volume",
    "keypad_operation_event_mask",
    "rf_operation_event_mask",
    "manual_operation_event_mask",
}


def infer_lock_profile(manufacturer: str | None, model: str | None) -> str:
    """Infer lock profile from manufacturer and model names."""
    manufacturer_l = (manufacturer or "").strip().lower()
    model_l = (model or "").strip().lower()

    if any(hint in manufacturer_l for hint in ID_LOCK_202_MANUFACTURER_HINTS):
        return LOCK_PROFILE_ID_LOCK_202_MULTI
    if any(hint in model_l for hint in ID_LOCK_202_MODEL_HINTS):
        return LOCK_PROFILE_ID_LOCK_202_MULTI

    return LOCK_PROFILE_GENERIC


def infer_lock_capabilities(
    lock_profile: str,
    attributes: Mapping[str, object] | None,
    has_cluster_write_service: bool,
) -> dict[str, bool]:
    """Infer lock capabilities from profile and available state attributes."""
    is_id_lock_202 = lock_profile == LOCK_PROFILE_ID_LOCK_202_MULTI
    attr_keys = set((attributes or {}).keys())
    has_probe_data = bool(attr_keys)

    supports_battery = (
        "battery_percentage" in attr_keys if has_probe_data else is_id_lock_202
    )
    supports_advanced_probe = bool(attr_keys & _ID_LOCK_ADVANCED_PROBE_ATTRIBUTES)
    supports_advanced_controls = (
        is_id_lock_202
        and has_cluster_write_service
        and (supports_advanced_probe or not has_probe_data)
    )

    return {
        CAP_SUPPORTS_BATTERY_PERCENTAGE: supports_battery,
        CAP_SUPPORTS_ID_LOCK_ADVANCED_CONTROLS: supports_advanced_controls,
    }

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

    def _discover_capabilities_for_lock_entity(
        self,
        lock_entity_id: str,
        lock_profile: str,
    ) -> dict[str, bool]:
        """Probe lock capabilities from entity attributes and service availability."""
        lock_state = self.hass.states.get(lock_entity_id)
        return infer_lock_capabilities(
            lock_profile=lock_profile,
            attributes=lock_state.attributes if lock_state else None,
            has_cluster_write_service=self.hass.services.has_service(
                "zha", "set_zigbee_cluster_attribute"
            ),
        )

    @staticmethod
    def _is_capability_supported(capabilities: Mapping[str, bool], capability: str) -> bool:
        """Return True when a capability is supported."""
        return bool(capabilities.get(capability, False))

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

        default_lock_entity = lock_entities[0]
        detected_profile = self._detect_profile_for_lock_entity(default_lock_entity)
        detected_capabilities = self._discover_capabilities_for_lock_entity(
            default_lock_entity,
            detected_profile,
        )

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

                selected_profile = user_input.get("lock_profile", LOCK_PROFILE_GENERIC)
                capabilities = self._discover_capabilities_for_lock_entity(
                    full_lock_entity_id,
                    selected_profile,
                )
                user_input[CONF_LOCK_CAPABILITIES] = capabilities

                if not self._is_capability_supported(
                    capabilities,
                    CAP_SUPPORTS_ID_LOCK_ADVANCED_CONTROLS,
                ):
                    user_input[CONF_ENABLE_ID_LOCK_ADVANCED_CONTROLS] = False

                if not self._is_capability_supported(
                    capabilities,
                    CAP_SUPPORTS_BATTERY_PERCENTAGE,
                ):
                    user_input.pop(CONF_BATTERY_LOW_THRESHOLD, None)

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
        schema_fields: dict = {
            vol.Required("slot_count", default=1): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=100)
            ),
            vol.Required("lock_name", default=default_lock_entity): vol.In(lock_entities),
            vol.Optional(
                "lock_profile",
                default=detected_profile,
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
        }

        if self._is_capability_supported(
            detected_capabilities,
            CAP_SUPPORTS_ID_LOCK_ADVANCED_CONTROLS,
        ):
            schema_fields[
                vol.Optional(
                    CONF_ENABLE_ID_LOCK_ADVANCED_CONTROLS,
                    default=DEFAULT_ENABLE_ID_LOCK_ADVANCED_CONTROLS,
                )
            ] = bool

        if self._is_capability_supported(
            detected_capabilities,
            CAP_SUPPORTS_BATTERY_PERCENTAGE,
        ):
            schema_fields[
                vol.Optional(
                    CONF_BATTERY_LOW_THRESHOLD,
                    default=DEFAULT_BATTERY_LOW_THRESHOLD,
                )
            ] = vol.All(vol.Coerce(int), vol.Range(min=5, max=100))

        schema = vol.Schema(schema_fields)

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

    def _discover_capabilities_for_lock_entity(
        self,
        lock_entity_id: str,
        lock_profile: str,
    ) -> dict[str, bool]:
        """Probe lock capabilities from entity attributes and service availability."""
        lock_state = self.hass.states.get(lock_entity_id)
        return infer_lock_capabilities(
            lock_profile=lock_profile,
            attributes=lock_state.attributes if lock_state else None,
            has_cluster_write_service=self.hass.services.has_service(
                "zha", "set_zigbee_cluster_attribute"
            ),
        )

    @staticmethod
    def _is_capability_supported(capabilities: Mapping[str, bool], capability: str) -> bool:
        """Return True when a capability is supported."""
        return bool(capabilities.get(capability, False))

    async def async_step_init(self, user_input=None):
        """Manage integration options."""
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
        lock_entity_id = f"lock.{self.config_entry.data.get('lock_name', '')}"
        current_capabilities = self._discover_capabilities_for_lock_entity(
            lock_entity_id,
            current_lock_profile,
        )

        if user_input is not None:
            submitted_profile = user_input.get("lock_profile", current_lock_profile)
            submitted_capabilities = self._discover_capabilities_for_lock_entity(
                lock_entity_id,
                submitted_profile,
            )
            merged_options = dict(self.config_entry.options)
            merged_options.update(user_input)

            if not self._is_capability_supported(
                submitted_capabilities,
                CAP_SUPPORTS_ID_LOCK_ADVANCED_CONTROLS,
            ):
                merged_options[CONF_ENABLE_ID_LOCK_ADVANCED_CONTROLS] = False

            if not self._is_capability_supported(
                submitted_capabilities,
                CAP_SUPPORTS_BATTERY_PERCENTAGE,
            ):
                merged_options.pop(CONF_BATTERY_LOW_THRESHOLD, None)

            merged_options[CONF_LOCK_CAPABILITIES] = submitted_capabilities
            return self.async_create_entry(title="", data=merged_options)

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

        schema_fields: dict = {
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
        }

        if self._is_capability_supported(
            current_capabilities,
            CAP_SUPPORTS_ID_LOCK_ADVANCED_CONTROLS,
        ):
            schema_fields[
                vol.Optional(
                    CONF_ENABLE_ID_LOCK_ADVANCED_CONTROLS,
                    default=current_enable_id_lock_advanced_controls,
                )
            ] = bool

        if self._is_capability_supported(
            current_capabilities,
            CAP_SUPPORTS_BATTERY_PERCENTAGE,
        ):
            schema_fields[
                vol.Optional(
                    CONF_BATTERY_LOW_THRESHOLD,
                    default=current_battery_low_threshold,
                )
            ] = vol.All(vol.Coerce(int), vol.Range(min=5, max=100))

        schema = vol.Schema(schema_fields)

        return self.async_show_form(step_id="init", data_schema=schema)
