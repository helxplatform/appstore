# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging
from time import sleep

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, JsonResponse

from tycho_jupyter import deployment

logger = logging.getLogger(__name__)


# Create your views here.
@login_required
def login_start(request):
    # view function when the start action is triggered from CommonsShare Apps Store from
    # which the user has already logged in to CommonsShare Apps Store directly
    # if "REMOTE_USER" in request.META:
    # request.session['REMOTE_USER'] = request.META["REMOTE_USER"]
    redirect_url = deploy(request)
    logger.info("TYcho  jUpyter")
    return HttpResponseRedirect(redirect_url)


@login_required
def deploy(request):
    print("Deploying service ...")
    request.META['REMOTE_USER'] = request.user.username
    try:
        redirect_url = deployment.deploy(request)
    except Exception as ex:
        return JsonResponse({'Exception while deploy': str(ex)})
    sleep(20)
    return redirect_url
