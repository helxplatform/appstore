# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from time import sleep

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, JsonResponse
from rest_framework.status import HTTP_500_INTERNAL_SERVER_ERROR

from apps_core_services.utils import check_authorization
from tycho_jupyter import deployment


# Create your views here.
@login_required
def login_start(request):
    # view function when the start action is triggered from CommonsShare Apps Store from
    # which the user has already logged in to CommonsShare Apps Store directly
    # if "REMOTE_USER" in request.META:
    # request.session['REMOTE_USER'] = request.META["REMOTE_USER"]
    redirect_url = deploy(request)
    return HttpResponseRedirect(redirect_url)


def start(request):
    print("entered start")
    # view function when the start action is triggered from CommonsShare
    auth_resp = check_authorization(request)
    if auth_resp.status_code != 200:
        return HttpResponseRedirect("/")
    else:
        # this is needed to strip out access token from URL
        return HttpResponseRedirect("/tycho_jupyter/login_start/")


@login_required
def deploy(request):
    print("Deploying service ...")
    request.META['REMOTE_USER'] = request.user.username
    try:
        redirect_url = deployment.deploy(request)
    except Exception as ex:
        return JsonResponse(data={'invalid ip_address or port from jupyter-datasacience deployment ': ex},
                            status=HTTP_500_INTERNAL_SERVER_ERROR)
    sleep(20)
    return redirect_url
