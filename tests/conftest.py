"""Test stubs for optional Home Assistant imports used by unit tests."""

import sys
import types
from pathlib import Path


# Ensure repository root is on sys.path so imports like
# custom_components.zigbee_lock_manager.* work during pytest collection.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# Provide lightweight Home Assistant stubs so we can import integration modules
# in unit tests without requiring the full Home Assistant runtime.
ha = types.ModuleType("homeassistant")
config_entries = types.ModuleType("homeassistant.config_entries")
helpers = types.ModuleType("homeassistant.helpers")
entity_registry = types.ModuleType("homeassistant.helpers.entity_registry")
device_registry = types.ModuleType("homeassistant.helpers.device_registry")
core = types.ModuleType("homeassistant.core")


class _ConfigFlow:
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()


class _OptionsFlow:
    pass


class _HomeAssistant:
    pass


def _noop_async_get(_hass):
    return None


config_entries.ConfigFlow = _ConfigFlow
config_entries.OptionsFlow = _OptionsFlow
core.HomeAssistant = _HomeAssistant
entity_registry.async_get = _noop_async_get
device_registry.async_get = _noop_async_get
helpers.entity_registry = entity_registry
helpers.device_registry = device_registry
ha.config_entries = config_entries
ha.helpers = helpers
ha.core = core

sys.modules.setdefault("homeassistant", ha)
sys.modules.setdefault("homeassistant.config_entries", config_entries)
sys.modules.setdefault("homeassistant.helpers", helpers)
sys.modules.setdefault("homeassistant.helpers.entity_registry", entity_registry)
sys.modules.setdefault("homeassistant.helpers.device_registry", device_registry)
sys.modules.setdefault("homeassistant.core", core)
