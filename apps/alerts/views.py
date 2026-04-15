from django.shortcuts import render


def alert_feed(request):
    return render(request, "alerts/feed.html")

