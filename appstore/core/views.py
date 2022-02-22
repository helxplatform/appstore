import logging
import os
from time import sleep
import uuid

from allauth.account.views import LoginView
from allauth.socialaccount.signals import pre_social_login

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.mail import EmailMessage
from django.dispatch import receiver
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.urls import reverse_lazy
from django.shortcuts import render
from django.views import generic
from django.views.generic.edit import FormView

import requests

from tycho.context import ContextFactory
from tycho.context import Principal

logger = logging.getLogger(__name__)

"""
Tycho context for application management.
Manages application metadata, discovers and invokes TychoClient, etc.
"""
tycho = ContextFactory.get(
    context_type=settings.TYCHO_MODE, product=settings.APPLICATION_BRAND
)


@receiver(pre_social_login)
def pre_login(sender, request, sociallogin, **kwargs):
    if sociallogin.token:
        access_token = sociallogin.token
        request.session["Authorization"] = f"Bearer {access_token}"
        logger.debug(f"----------> Adding Bearer token to the user session")


def login_whitelist(request):
    full_brand = get_brand_details(settings.APPLICATION_BRAND)["name"]
    logger.debug(
        f"-- login_whitelist: brand: {settings.APPLICATION_BRAND}, full_brand: {full_brand}"
    )
    return render(
        request,
        "core/whitelist.html",
        {"brand": settings.APPLICATION_BRAND, "full_brand": full_brand},
    )


def get_brand_details(brand):
    """
    Any special reason they can't all just be called logo.png?
    (since they're already in namespaced subdirectories)
    Sure would cut down on unproductive complexity here.
    """
    return {
        "braini": {"name": "BRAIN-I", "logo": "braini-lg-gray.png"},
        "scidas": {"name": "SciDAS", "logo": "scidas-logo-sm.png"},
        "catalyst": {"name": "BioData Catalyst", "logo": "bdc-logo.svg"},
        "restartr": {
            "name": "UNC Restarting Research",
            "logo": "restartingresearch.png",
        },
        "heal": {"name": "NIH Heal Initiative", "logo": "logo.png"},
        "argus": {"name": "Argus Array", "logo": "argus-array-256.png"},
        "eduhelx": {"name": "EduHelx", "logo": "logo.png"},
    }[brand]


def get_access_token(request):
    access_token = ""
    try:
        auth_string = request.session["Authorization"]
        if auth_string and ("Bearer" in auth_string):
            access_token = auth_string.split(" ")[1]
    except Exception as e:
        logger.debug("----------> Failed getting access token. ")
        pass
    return access_token


@login_required
def auth(request):
    """Provide an endpoint for getting the user identity.
    Supports the use case where a reverse proxy like nginx is being
    used to test authentication of a principal before proxying a request upstream."""
    if request.user and request.user.is_authenticated:
        try:
            response = HttpResponse(content_type="application/json", status=200)
            response["REMOTE_USER"] = request.user
            access_token = get_access_token(request)
            response["ACCESS_TOKEN"] = access_token
            logger.debug(
                f"----------> remote user and corresponding access token added to the response ----- {response['REMOTE_USER']}"
            )
        except Exception as e:
            response = HttpResponse(content_type="application/json", status=403)
            response["REMOTE_USER"] = request.user
            logger.debug(
                f"----------> exception with the remote user ----- {request.user}"
            )
    else:
        response = HttpResponse(content_type="application/json", status=403)
        response["REMOTE_USER"] = request.user
        logger.debug(
            f"----------> user is not authenticated on the server ----- {request.user}"
        )
    return response

def custom404(request, exception):
    """
    For most routes serve the standard 404 page.

    Private routes indicate a route to a user instantiated app. If a 404 is
    raised on one of these routes it means the app has stopped/is no longer
    available. We want to notify the user and let them return to the app page.
    """

    if "private" in request.path:
        template_name = "private404.html"
    else:
        template_name = "404.html"
    context = {"req_path": request.path}
    return render(request, template_name, context=context, status=404)
