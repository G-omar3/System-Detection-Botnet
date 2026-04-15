from datetime import datetime

from django.http import HttpResponse

from ml.model.pipeline import get_runtime


RUNTIME = get_runtime()


def export_csv(request):
    source = request.GET.get("source", "sample")
    result = RUNTIME.analyze_live(request.GET.dict()) if source == "live" else RUNTIME.analyze_sample(request.GET.dict())
    content = RUNTIME.export_csv(result)
    stamp = datetime.now().strftime("%Y-%m-%d")
    response = HttpResponse(content, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f"attachment; filename=netwatch_soc_report_{stamp}.csv"
    return response


def export_pdf(request):
    source = request.GET.get("source", "sample")
    result = RUNTIME.analyze_live(request.GET.dict()) if source == "live" else RUNTIME.analyze_sample(request.GET.dict())
    content = RUNTIME.export_pdf(result)
    stamp = datetime.now().strftime("%Y-%m-%d")
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = f"attachment; filename=netwatch_soc_report_{stamp}.pdf"
    return response
