from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)


def root(request):
    return JsonResponse(
        {"service": "detasawy-backend", "status": "ok", "docs": "/api/docs"},
    )


def health(request):
    return JsonResponse({"service": "detasawy-backend", "status": "ok"})


urlpatterns = [
    path("", root),
    path("api/health", health),
    path("admin/", admin.site.urls),
    path("api/", include("apps.identity.urls")),
    path("api/ref/", include("apps.ref.urls")),
    path("api/schema", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("api/redoc", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
