from custom_components.zigbee_lock_manager.config_flow import (
    infer_lock_capabilities,
    infer_lock_profile,
)
from custom_components.zigbee_lock_manager.const import (
    CAP_SUPPORTS_BATTERY_PERCENTAGE,
    CAP_SUPPORTS_ID_LOCK_ADVANCED_CONTROLS,
    LOCK_PROFILE_GENERIC,
    LOCK_PROFILE_ID_LOCK_202_MULTI,
)


def test_infer_profile_detects_id_lock_from_manufacturer():
    assert infer_lock_profile("Datek", "some model") == LOCK_PROFILE_ID_LOCK_202_MULTI


def test_infer_profile_detects_id_lock_from_model():
    assert infer_lock_profile("other", "ID Lock 202 Multi") == LOCK_PROFILE_ID_LOCK_202_MULTI


def test_infer_profile_defaults_to_generic():
    assert infer_lock_profile("Acme", "Model X") == LOCK_PROFILE_GENERIC


def test_infer_capabilities_for_id_lock_with_attributes_and_zha_write():
    capabilities = infer_lock_capabilities(
        lock_profile=LOCK_PROFILE_ID_LOCK_202_MULTI,
        attributes={
            "battery_percentage": 64,
            "sound_volume": 5,
        },
        has_cluster_write_service=True,
    )

    assert capabilities[CAP_SUPPORTS_BATTERY_PERCENTAGE] is True
    assert capabilities[CAP_SUPPORTS_ID_LOCK_ADVANCED_CONTROLS] is True


def test_infer_capabilities_disables_advanced_when_write_service_missing():
    capabilities = infer_lock_capabilities(
        lock_profile=LOCK_PROFILE_ID_LOCK_202_MULTI,
        attributes={"battery_percentage": 42, "sound_volume": 3},
        has_cluster_write_service=False,
    )

    assert capabilities[CAP_SUPPORTS_BATTERY_PERCENTAGE] is True
    assert capabilities[CAP_SUPPORTS_ID_LOCK_ADVANCED_CONTROLS] is False


def test_infer_capabilities_uses_safe_id_lock_fallback_without_probe_data():
    capabilities = infer_lock_capabilities(
        lock_profile=LOCK_PROFILE_ID_LOCK_202_MULTI,
        attributes=None,
        has_cluster_write_service=True,
    )

    assert capabilities[CAP_SUPPORTS_BATTERY_PERCENTAGE] is True
    assert capabilities[CAP_SUPPORTS_ID_LOCK_ADVANCED_CONTROLS] is True


def test_infer_capabilities_generic_lock_disables_id_lock_features():
    capabilities = infer_lock_capabilities(
        lock_profile=LOCK_PROFILE_GENERIC,
        attributes={"battery_percentage": 75, "sound_volume": 2},
        has_cluster_write_service=True,
    )

    assert capabilities[CAP_SUPPORTS_BATTERY_PERCENTAGE] is True
    assert capabilities[CAP_SUPPORTS_ID_LOCK_ADVANCED_CONTROLS] is False
