import json
from datetime import datetime

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from ml_model.runtime import RUNTIME


def index(request):
    return render(request, "dashboard/index.html")


def sample(request):
    return JsonResponse({"csv": RUNTIME.load_sample_csv()})


@csrf_exempt
def analyze(request):
    if request.method == "POST":
        payload = json.loads(request.body.decode("utf-8") or "{}")
        csv_text = payload.get("csv") or RUNTIME.load_sample_csv()
        config = payload.get("config") or {}
        rows = RUNTIME.analyzer.load_rows(csv_text)
        return JsonResponse(RUNTIME.analyze_rows(rows, config))
    return JsonResponse(RUNTIME.analyze_sample(request.GET.dict()))


@csrf_exempt
def live_start(request):
    payload = json.loads(request.body.decode("utf-8") or "{}")
    live = RUNTIME.start_live(payload.get("mode", "http"), payload.get("host", "127.0.0.1"), int(payload.get("port", 5055)))
    return JsonResponse({"ok": live.get("mode") != "stopped", "live": live})


@csrf_exempt
def live_stop(request):
    RUNTIME.stop_live()
    return JsonResponse({"ok": True, "live": RUNTIME.live_store.status()})


def live_status(request):
    return JsonResponse(RUNTIME.live_store.status())


def live_analyze(request):
    result = RUNTIME.analyze_live(request.GET.dict())
    result["live"] = RUNTIME.live_store.status()
    return JsonResponse(result)


@csrf_exempt
def live_ingest(request):
    payload = json.loads(request.body.decode("utf-8") or "{}")
    rows = payload.get("rows")
    if isinstance(rows, list):
        RUNTIME.live_store.add_rows(rows)
    elif isinstance(payload.get("row"), dict):
        RUNTIME.live_store.add_row(payload["row"])
    elif isinstance(payload, dict):
        RUNTIME.live_store.add_row(payload)
    return JsonResponse({"ok": True, "live": RUNTIME.live_store.status()})


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
