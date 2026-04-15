from django.urls import path

from . import views


urlpatterns = [
    path("", views.index, name="index"),
    path("api/sample", views.sample, name="sample"),
    path("api/analyze", views.analyze, name="analyze"),
    path("api/live/start", views.live_start, name="live_start"),
    path("api/live/stop", views.live_stop, name="live_stop"),
    path("api/live/status", views.live_status, name="live_status"),
    path("api/live/analyze", views.live_analyze, name="live_analyze"),
    path("api/live/ingest", views.live_ingest, name="live_ingest"),
    path("api/export/report.csv", views.export_csv, name="export_csv"),
    path("api/export/report.pdf", views.export_pdf, name="export_pdf"),
]
