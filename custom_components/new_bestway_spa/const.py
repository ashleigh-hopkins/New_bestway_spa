from enum import Enum

DOMAIN = "new_bestway_spa"

CONF_APPID = "appid"
CONF_APPSECRET = "appsecret"
CONF_DEVICE_ID = "device_id"
CONF_PRODUCT_ID = "product_id"
CONF_REGISTRATION_ID = "registration_id"
CONF_VISITOR_ID = "visitor_id"
CONF_CLIENT_ID = "client_id"


class Icon(str, Enum):
    """MDI icons for entities."""

    BUBBLES = "mdi:chart-bubble"
    FILTER = "mdi:filter"
    HEATER = "mdi:radiator"
    HYDROJET = "mdi:turbine"
    LOCK = "mdi:lock"
    POWER = "mdi:power"
    THERMOMETER = "mdi:thermometer"
    CALENDAR = "mdi:calendar-clock"
