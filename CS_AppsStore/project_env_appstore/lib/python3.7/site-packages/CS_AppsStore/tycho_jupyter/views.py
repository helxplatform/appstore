# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.contrib.auth.decorators import login_required
from apps_core_services.utils import check_authorization
from django.http import HttpResponseRedirect, JsonResponse, HttpResponse
from django.shortcuts import render
from rest_framework.status import HTTP_200_OK, HTTP_500_INTERNAL_SERVER_ERROR, \
    HTTP_400_BAD_REQUEST
import json

from tycho_jupyter import deployment

# Create your views here.
@login_required
def login_start(request):
    # view function when the start action is triggered from CommonsShare Apps Store from
    # which the user has already logged in to CommonsShare Apps Store directly
    redirect_url = deploy(request)
    return HttpResponseRedirect(redirect_url)


def start(request):
    print("entered here")
    # view function when the start action is triggered from CommonsShare
    auth_resp = check_authorization(request)
    if auth_resp.status_code != 200:
        return HttpResponseRedirect("/")
    else:
        # this is needed to strip out access token from URL
        return HttpResponseRedirect("/tycho_jupyter/login_start/")


@login_required
def deploy(request):
    print("deploying service...")
    try:
        redirect_url = deployment.deploy()
    except Exception as ex:
        return JsonResponse(data={'invalid ip_address or port from jupyter-datasacience deployment ': ex},
                            status=HTTP_500_INTERNAL_SERVER_ERROR)

    return redirect_url
