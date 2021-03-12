from django.shortcuts import render


def spa(request):
    return render(request, "spa/index.html")