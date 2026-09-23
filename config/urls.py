from django.conf import settings
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path, re_path
from apps.corpus.media import legacy_prompt_media
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
    path("api/", include("apps.corpus.urls")),
    path("api/", include("apps.portal.urls")),
    path("api/admin/", include("apps.ref.staff_urls")),
    path("api/ref/", include("apps.ref.urls")),
    path("api/schema", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("api/redoc", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

# Existing prompt links keep working; arbitrary storage paths never get served.
urlpatterns += [re_path(r"^media/(?P<path>.*)$", legacy_prompt_media)]
