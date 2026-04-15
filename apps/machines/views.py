from django.shortcuts import render


def machine_list(request):
    return render(request, "machines/list.html")


def machine_detail(request, machine_ip):
    return render(request, "machines/detail.html", {"machine_ip": machine_ip})

