import re
import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN, LOCK_PROFILE_GENERIC, LOCK_PROFILE_OPTIONS
import logging

_LOGGER = logging.getLogger(__name__)

# Permitted characters for a lock object_id derived from a HA entity ID.
# HA restricts object IDs to lowercase letters, digits, underscores, and hyphens.
_SAFE_NAME_RE = re.compile(r'^[a-z0-9_\-]+$')

class LockCodeFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the configuration flow for Zigbee Lock Manager."""

    VERSION = 1.0

    @staticmethod
    def async_get_options_flow(config_entry):
        """Get the options flow handler."""
        return LockCodeOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        # Fetch available lock entities (assume they are in the format lock.some_lock_name)
        lock_entities = [entity.entity_id for entity in self.hass.states.async_all("lock")]

        # Handle the case where no lock entities are available
        if not lock_entities:
            errors["base"] = "no_locks"
            _LOGGER.warning("No locks found during config flow")
            return self.async_show_form(
                step_id="user",
                errors=errors,
                description_placeholders={"error": "No locks found in your Home Assistant instance."},
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
                # Store the processed lock_name instead of the full entity ID
                user_input["lock_name"] = lock_name

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
            vol.Optional("lock_profile", default=LOCK_PROFILE_GENERIC): vol.In(LOCK_PROFILE_OPTIONS),
        })

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class LockCodeOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Zigbee Lock Manager options."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage integration options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_slot_count = self.config_entry.options.get(
            "slot_count", self.config_entry.data.get("slot_count", 1)
        )
        current_lock_profile = self.config_entry.options.get(
            "lock_profile",
            self.config_entry.data.get("lock_profile", LOCK_PROFILE_GENERIC),
        )

        schema = vol.Schema({
            vol.Required("slot_count", default=current_slot_count): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=100)
            ),
            vol.Optional("lock_profile", default=current_lock_profile): vol.In(
                LOCK_PROFILE_OPTIONS
            ),
        })

        return self.async_show_form(step_id="init", data_schema=schema)
