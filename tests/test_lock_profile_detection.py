from custom_components.zigbee_lock_manager.config_flow import infer_lock_profile
from custom_components.zigbee_lock_manager.const import (
    LOCK_PROFILE_GENERIC,
    LOCK_PROFILE_ID_LOCK_202_MULTI,
)


def test_infer_profile_detects_id_lock_from_manufacturer():
    assert infer_lock_profile("Datek", "some model") == LOCK_PROFILE_ID_LOCK_202_MULTI


def test_infer_profile_detects_id_lock_from_model():
    assert infer_lock_profile("other", "ID Lock 202 Multi") == LOCK_PROFILE_ID_LOCK_202_MULTI


def test_infer_profile_defaults_to_generic():
    assert infer_lock_profile("Acme", "Model X") == LOCK_PROFILE_GENERIC
