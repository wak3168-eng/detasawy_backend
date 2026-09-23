from rest_framework.authentication import SessionAuthentication


class CookieSessionAuthentication(SessionAuthentication):
    """Reject CSRF on anonymous mutations too, especially the login endpoint."""

    def authenticate(self, request):
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            self.enforce_csrf(request)
        return super().authenticate(request)

    def authenticate_header(self, request):
        return "Session"
