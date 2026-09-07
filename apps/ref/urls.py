from django.urls import path

from apps.ref import views

urlpatterns = [
    path("provinces", views.provinces),
    path("districts", views.districts),
    path("tehsils", views.tehsils),
    path("tribes", views.tribes),
    path("languages", views.languages),
]
