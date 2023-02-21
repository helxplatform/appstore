import logging

from allauth.socialaccount.signals import pre_social_login

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.dispatch import receiver
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.shortcuts import render

from tycho.context import ContextFactory

from urllib.parse import urljoin

logger = logging.getLogger(__name__)

"""
Tycho context for application management.
Manages application metadata, discovers and invokes TychoClient, etc.
"""
contextFactory = ContextFactory()
if settings.EXTERNAL_TYCHO_APP_REGISTRY_ENABLED == "false":
    logger.debug (f"-- appstore.appstore.core.views.py: EXTERNAL_TYCHO_APP_REGISTRY_ENABLED is 'false', using Tycho built-in app registry file")
    tycho = contextFactory.get(
            context_type=settings.TYCHO_MODE, product=settings.APPLICATION_BRAND
    )
else:
    logger.debug (f"-- appstore.appstore.core.views.py: EXTERNAL_TYCHO_APP_REGISTRY_REPO is {settings.EXTERNAL_TYCHO_APP_REGISTRY_REPO}, EXTERNAL_TYCHO_APP_REGISTRY_BRANCH is {settings.EXTERNAL_TYCHO_APP_REGISTRY_BRANCH}, using external app registry file")
    # urljoin might not work as planned if the first part doesn't end with a slash.
    tycho_config_url = urljoin(settings.EXTERNAL_TYCHO_APP_REGISTRY_REPO, settings.EXTERNAL_TYCHO_APP_REGISTRY_BRANCH)
    logger.debug (f"tycho_config_url: {tycho_config_url}")
    tycho = contextFactory.get(
            context_type=settings.TYCHO_MODE, product=settings.APPLICATION_BRAND, tycho_config_url=tycho_config_url
    )


@receiver(pre_social_login)
def pre_login(sender, request, sociallogin, **kwargs):
    if sociallogin.token:
        access_token = sociallogin.token
        request.session["Authorization"] = f"Bearer {access_token}"
        logger.debug(f"----------> Adding Bearer token to the user session")


def get_brand_details(brand):
    """
    Any special reason they can't all just be called logo.png?
    (since they're already in namespaced subdirectories)
    Sure would cut down on unproductive complexity here.
    """
    return {
        "helx": {"name": "HeLx", "logo": "logo.png"},
        "braini": {"name": "BRAIN-I", "logo": "logo.png"},
        "scidas": {"name": "SciDAS", "logo": "logo.png"},
        "bdc": {"name": "BioData Catalyst", "logo": "logo.svg"},
        "restartr": {
            "name": "UNC Restarting Research",
            "logo": "logo.png",
        },
        "heal": {"name": "NIH Heal Initiative", "logo": "logo.png"},
        "argus": {"name": "Argus Array", "logo": "logo.png"},
        "eduhelx": {"name": "EduHelx", "logo": "logo.png"},
        "testing": {"name": "Testing", "logo": "logo.png"},
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
