from django.conf import settings
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class CookieSessionScheme(OpenApiAuthenticationExtension):
    target_class = "apps.identity.authentication.CookieSessionAuthentication"
    name = "cookieAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey", "in": "cookie", "name": settings.SESSION_COOKIE_NAME,
            "description": "Log in with a CSRF token to set the HttpOnly session cookie. Unsafe requests also require X-CSRFToken.",
        }
