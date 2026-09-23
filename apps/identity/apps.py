from django.apps import AppConfig


class IdentityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.identity"
    verbose_name = "Identity"

    def ready(self):
        from . import schema, sessions  # noqa: F401
