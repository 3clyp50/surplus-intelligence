from usr.plugins.surplus_intelligence.helpers.routing import validate_config


def save_plugin_config(settings, **kwargs):
    validate_config(settings)
    return settings
