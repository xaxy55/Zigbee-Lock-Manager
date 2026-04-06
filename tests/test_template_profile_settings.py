from custom_components.zigbee_lock_manager.const import (
    LOCK_PROFILE_GENERIC,
    LOCK_PROFILE_ID_LOCK_202_MULTI,
)
from custom_components.zigbee_lock_manager.zha_manager import (
    lock_slot_file_prefix,
    profile_render_settings,
)
from pathlib import Path

import jinja2


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


def _render_template_for_profile(lock_profile: str) -> str:
    template_path = Path(__file__).resolve().parents[1] / "custom_components" / "zigbee_lock_manager" / "zha_manager_template.yaml"
    template = jinja2.Template(template_path.read_text())
    return template.render(
        lock_name="front_door",
        slot=1,
        slot_count=2,
        code_label="Lock PIN",
        code_max=10,
        code_validation_regex="^[0-9]{4,10}$",
        invalid_code_message="Invalid code",
        enable_notifications=True,
        enable_presence_automation=False,
        lock_profile=lock_profile,
        enable_id_lock_advanced_controls=False,
        battery_low_threshold=30,
        activity_event_count=6,
    )


def test_id_lock_template_includes_door_state_error_alert_automation():
    rendered = _render_template_for_profile(LOCK_PROFILE_ID_LOCK_202_MULTI)

    assert "ID Lock 202 Door Error Alert" in rendered
    assert "attribute: door_state" in rendered
    assert "door_state_normalized in ['jammed', 'forced open', 'unspecified error']" in rendered


def test_generic_template_excludes_id_lock_door_state_error_alert_automation():
    rendered = _render_template_for_profile(LOCK_PROFILE_GENERIC)

    assert "ID Lock 202 Door Error Alert" not in rendered
