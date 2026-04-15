from django.urls import path

from . import views


urlpatterns = [
    path("machines/", views.machine_list, name="machine_list"),
    path("machines/<path:machine_ip>/", views.machine_detail, name="machine_detail"),
]

