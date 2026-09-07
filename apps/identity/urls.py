from django.urls import path

from apps.identity import views

urlpatterns = [
    path("auth/signup", views.signup),
    path("auth/login", views.login),
    path("auth/logout", views.logout),
    path("auth/me", views.me),
    path("profile", views.profile),
]
