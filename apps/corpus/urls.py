from django.urls import path

from apps.corpus import views

urlpatterns = [
    path("prompts", views.prompts),
    path("prompts/<int:pk>/words", views.prompt_words),
    path("contributions", views.contribute),
    path("contributions/today", views.today),
]
