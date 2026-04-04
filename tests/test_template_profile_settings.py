from custom_components.zigbee_lock_manager.const import (
    LOCK_PROFILE_GENERIC,
    LOCK_PROFILE_ID_LOCK_202_MULTI,
)
from custom_components.zigbee_lock_manager.zha_manager import (
    lock_slot_file_prefix,
    profile_render_settings,
)


def test_profile_render_settings_for_id_lock():
    settings = profile_render_settings(LOCK_PROFILE_ID_LOCK_202_MULTI)
    assert settings["code_label"] == "Lock PIN"
    assert settings["code_max"] == 10
    assert settings["code_validation_regex"] == "^[0-9]{4,10}$"


def test_profile_render_settings_for_generic_lock():
    settings = profile_render_settings(LOCK_PROFILE_GENERIC)
    assert settings["code_label"] == "Lock Code"
    assert settings["code_max"] == 10
    assert settings["code_validation_regex"] == "^.{1,10}$"


def test_slot_file_prefix_generation():
    assert lock_slot_file_prefix("front_door") == "front_door_slot_"
    assert lock_slot_file_prefix("level.lock") == "level_lock_slot_"
