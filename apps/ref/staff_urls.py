from django.urls import path

from apps.ref import staff_views

urlpatterns = [
    path("overview", staff_views.overview),
    path("suggestions", staff_views.suggestions),
    path("suggestions/<int:pk>", staff_views.suggestion_action),
]
