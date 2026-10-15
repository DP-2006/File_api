from django.apps import AppConfig

def ready(self):
    from . import signals  # noqa: F401


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
