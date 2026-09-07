from django.urls import path

from apps.corpus import views

urlpatterns = [
    path("prompts", views.prompts),
]
