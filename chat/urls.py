from django.urls import path

from . import views

app_name = "chat"

urlpatterns = [
    path("chat/", views.index, name="index"),
    path("sessions/", views.session_list, name="session_list"),
    path("sessions/new/", views.session_new, name="session_new"),
    path("sessions/<int:pk>/", views.session_detail, name="session"),
    path("sessions/<int:pk>/rename/", views.session_rename, name="session_rename"),
    path("sessions/<int:pk>/delete/", views.session_delete, name="session_delete"),
    path("sessions/<int:pk>/model/", views.session_set_model, name="session_set_model"),
    path("sessions/<int:pk>/memories/", views.session_toggle_memories, name="session_toggle_memories"),
    path("sessions/<int:pk>/send/", views.send, name="send"),
]
