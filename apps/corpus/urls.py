from django.urls import path

from apps.corpus import media, staff_views, views

urlpatterns = [
    path("private/contributions/<int:pk>/audio", media.contribution_audio),
    path("private/profiles/<int:pk>/photo", media.profile_photo),
    path("media/prompts/<int:pk>", media.prompt_media),
    path("prompts", views.prompts),
    path("prompts/<int:pk>/words", views.prompt_words),
    path("blob/<str:sha>", views.blob),
    path("contributions", views.contribute),
    path("contributions/today", views.today),
    path("admin/dataset", staff_views.dataset),
    path("admin/contributions", staff_views.staff_contributions),
    path("admin/prompts", staff_views.staff_prompts),
    path("admin/prompts/batch", staff_views.staff_prompts_batch),
    path("admin/prompts/<int:pk>", staff_views.staff_prompt_update),
]
