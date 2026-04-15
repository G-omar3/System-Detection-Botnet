from django.urls import path

from . import views


urlpatterns = [
    path("api/export/report.csv", views.export_csv, name="export_csv"),
    path("api/export/report.pdf", views.export_pdf, name="export_pdf"),
]

