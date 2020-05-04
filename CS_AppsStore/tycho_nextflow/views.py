# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from time import sleep

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, JsonResponse

from tycho_nextflow import deployment


# Create your views here.
@login_required
def login_start(request):
    # view function when the start action is triggered from CommonsShare Apps Store from
    # which the user has already logged in to CommonsShare Apps Store directly
    redirect_url = deploy(request)
    messages.success(request, 'Launching Nextflow')
    return HttpResponseRedirect(redirect_url)


@login_required
def deploy(request):
    print("deploying service...")
    request.META['REMOTE_USER'] = request.user.username
    try:
        redirect_url = deployment.deploy(request)
        float("89292.0--0")
    except Exception as ex:
        return JsonResponse({'Exception while deploy': str(ex)})
    sleep(20)
    return redirect_url
