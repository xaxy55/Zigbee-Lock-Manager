DOMAIN = "zigbee_lock_manager"

CONF_ENABLE_NOTIFICATIONS = "enable_notifications"
CONF_ENABLE_PRESENCE_AUTOMATION = "enable_presence_automation"
CONF_ACTIVITY_EVENT_COUNT = "activity_event_count"

DEFAULT_ENABLE_NOTIFICATIONS = False
DEFAULT_ENABLE_PRESENCE_AUTOMATION = False
DEFAULT_ACTIVITY_EVENT_COUNT = 6

LOCK_PROFILE_GENERIC = "generic"
LOCK_PROFILE_ID_LOCK_202_MULTI = "id_lock_202_multi"

LOCK_PROFILE_OPTIONS = {
    LOCK_PROFILE_GENERIC: "Generic ZHA Lock",
    LOCK_PROFILE_ID_LOCK_202_MULTI: "ID Lock 202 Multi",
}

ID_LOCK_202_MANUFACTURER_HINTS = ("datek", "id lock")
ID_LOCK_202_MODEL_HINTS = (
    "id lock 202",
    "id lock 202 multi",
    "idlock 202",
)
