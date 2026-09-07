from django.urls import path

from apps.identity import staff_views, views

urlpatterns = [
    path("auth/signup", views.signup),
    path("auth/login", views.login),
    path("auth/logout", views.logout),
    path("auth/me", views.me),
    path("profile", views.profile),
    path("admin/users", staff_views.users),
    path("admin/users/role", staff_views.set_role),
]
