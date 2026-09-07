from django.urls import path

from apps.portal import staff_views, views

urlpatterns = [
    path("campaigns", views.campaigns),
    path("stats", views.public_stats),
    path("leaderboard/districts", views.district_leaderboard),
    path("me/stats", views.my_stats),
    path("admin/campaigns", staff_views.staff_campaigns),
    path("admin/campaigns/<int:pk>/end", staff_views.staff_campaign_end),
]
