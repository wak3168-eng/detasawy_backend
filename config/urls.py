from django.conf import settings
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path, re_path
from django.views.static import serve as media_serve
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
    path("api/ref/", include("apps.ref.urls")),
    path("api/schema", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("api/redoc", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

if not settings.USE_S3_MEDIA:
    urlpatterns += [
        re_path(
            r"^media/(?P<path>.*)$",
            media_serve,
            {"document_root": settings.MEDIA_ROOT},
        ),
    ]
