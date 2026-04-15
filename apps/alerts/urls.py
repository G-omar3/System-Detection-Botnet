from django.urls import path

from . import views


urlpatterns = [
    path("alerts/", views.alert_feed, name="alert_feed"),
]

