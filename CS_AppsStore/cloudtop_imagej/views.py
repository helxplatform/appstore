# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from time import sleep

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, JsonResponse

from cloudtop_imagej import deployment


# Create your views here.
@login_required
def login_start(request):
    # view function when the start action is triggered from CommonsShare Apps Store from
    # which the user has already logged in to CommonsShare Apps Store directly
    redirect_url = deploy(request)
    messages.success(request, 'Launching CloudTop/ImageJ')
    return HttpResponseRedirect(redirect_url)


@login_required
def deploy(request):
    print("deploying service...")

    print(f"USERNAME: {request.user.username}")
    request.META['REMOTE_USER'] = request.user.username
    print(f"REQUEST META: {request.META}")
    request.session['REMOTE_USER'] = request.user.username
    try:
        redirect_url = deployment.deploy(request)
    except Exception as ex:
        return JsonResponse({'Exception while deploy': str(ex)})

    sleep(20)
    return redirect_url
