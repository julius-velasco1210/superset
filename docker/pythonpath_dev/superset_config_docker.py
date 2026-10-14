# Local POC overrides (dummy data only, not for production).
# Loaded last by docker/pythonpath_dev/superset_config.py.

FEATURE_FLAGS = {
    "MOBILE_CONSUMPTION_MODE": True,
    "EMBEDDED_SUPERSET": True,
}

GUEST_ROLE_NAME = "Gamma"

TALISMAN_ENABLED = False

ENABLE_CORS = True
CORS_OPTIONS = {
    "supports_credentials": True,
    "allow_headers": ["*"],
    "resources": ["*"],
    "origins": ["*"],
}
