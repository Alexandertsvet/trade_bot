from django.urls import path

from homepage.views import HomeView, get_task_status

app_name = "homepage"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("task-status/<str:task_id>/", get_task_status, name="task"),
]
