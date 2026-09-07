from django.urls import path

from apps.portal import views

urlpatterns = [
    path("campaigns", views.campaigns),
]
