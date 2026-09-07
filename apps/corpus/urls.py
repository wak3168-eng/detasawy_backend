from django.urls import path

from apps.corpus import staff_views, views

urlpatterns = [
    path("prompts", views.prompts),
    path("prompts/<int:pk>/words", views.prompt_words),
    path("contributions", views.contribute),
    path("contributions/today", views.today),
    path("admin/prompts", staff_views.staff_prompts),
    path("admin/prompts/<int:pk>", staff_views.staff_prompt_update),
]
