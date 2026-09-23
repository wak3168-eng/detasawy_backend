from django.http import JsonResponse
from django.utils.cache import patch_vary_headers
from .throttles import client_ip, consume


class PrivateResponseMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == "/admin/login/" and request.method == "POST":
            email = request.POST.get("username", "").strip().casefold()
            wait = max(
                consume("login-ip", client_ip(request), 10, 60),
                consume("login-account", email, 10, 60),
                consume("login-ip-hour", client_ip(request), 100, 3600),
                consume("login-account-hour", email, 30, 3600),
            )
            if wait:
                response = JsonResponse({"error": "Too many attempts. Try again later."}, status=429)
                response["Retry-After"] = str(wait)
                response["Cache-Control"] = "private, no-store"
                return response
        response = self.get_response(request)
        if request.path.startswith(("/api/auth/", "/api/profile", "/api/private/", "/api/admin/", "/media/")) or (
            request.path.startswith("/api/") and request.user.is_authenticated
        ):
            response["Cache-Control"] = "private, no-store"
            patch_vary_headers(response, ("Cookie",))
        return response
