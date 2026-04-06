import logging
import re

from allauth.socialaccount.signals import pre_social_login

from django.contrib.auth.decorators import login_required
from django.dispatch import receiver
from django.http import  HttpResponse, JsonResponse
from django.shortcuts import render, redirect

from core.models import UserIdentityToken

logger = logging.getLogger(__name__)

_PRIVATE_APP_PATH_RE = re.compile(
    r"^/private/(?P<app_id>[^/]+)/(?P<username>[^/]+)/(?P<sid>[^/]+)(?P<rest>/.*)?$"
)


@receiver(pre_social_login)
def pre_login(sender, request, sociallogin, **kwargs):
    if sociallogin.token:
        access_token = sociallogin.token
        request.session["Authorization"] = f"Bearer {access_token}"
        logger.debug(f'{"----------> Adding Bearer token to the user session"}')


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
        "restartr": { "name": "UNC Restarting Research", "logo": "logo.png", },
        "heal": {"name": "NIH Heal Initiative", "logo": "logo.png"},
        "argus": {"name": "Argus Array", "logo": "logo.png"},
        "eduhelx": {"name": "EduHelx", "logo": "logo.png"},
        "eduhelx-dev": {"name": "EduHelx", "logo": "logo.png"},
        "eduhelx-dev-student": {"name": "EduHelx", "logo": "logo.png"},
        "eduhelx-dev-professor": {"name": "EduHelx", "logo": "logo.png"},
        "eduhelx-student": {"name": "EduHelx", "logo": "logo.png"},
        "eduhelx-professor": {"name": "EduHelx", "logo": "logo.png"},
        "testing": {"name": "Testing", "logo": "logo.png"},
        "ordrd": {"name": "Ordr D", "logo": "logo.png"},
    }[brand]


def get_access_token(request):
    access_token = ""
    try:
        auth_string = request.session["Authorization"]
        if auth_string and ("Bearer" in auth_string):
            access_token = auth_string.split(" ")[1]
    except Exception as e:
        logger.debug(f"----------> {e.__class__.__name__}: Failed getting access token.")
        pass
    return access_token


def auth_identity(request):
    auth_header = request.headers.get("Authorization")
    try:
        bearer, raw_token = auth_header.split(" ")
        if bearer != "Bearer": raise ValueError()
    except:
        return HttpResponse("Authorization header must be structured as 'Bearer {token}'", status=400)

    try:
        token = UserIdentityToken.objects.get(token=raw_token)
        if not token.valid:
            return HttpResponse("The token is expired. Try restarting the app.", status=401)
        remote_user = token.user.get_username()
        response = HttpResponse(remote_user, status=200)
        response["REMOTE_USER"] = remote_user
        response["ACCESS_TOKEN"] = token.token
        return response
    except UserIdentityToken.DoesNotExist:
        return HttpResponse("The token does not exist. Try restarting the app.", status=401)


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
                f"----------> exception {e.__class__.__name__} \
                with the remote user ----- {request.user} "
            )
    else:
        response = HttpResponse(content_type="application/json", status=403)
        response["REMOTE_USER"] = request.user
        logger.debug(
            f"----------> user is not authenticated on the server ----- {request.user}"
        )
    return response

def _get_helxinst_manager():
    from api.v1.views import _get_helxinst_mgr

    return _get_helxinst_mgr()


def _resolve_private_redirect_path(path):
    match = _PRIVATE_APP_PATH_RE.match(path)
    if match is None:
        return None

    app_id = match.group("app_id")
    sid = match.group("sid")
    rest = match.group("rest") or ""

    helxinst = _get_helxinst_manager().get(f"{app_id}-{sid}")
    if helxinst is None:
        return None

    controller_uuid = (helxinst.get("status") or {}).get("uuid")
    if not controller_uuid or controller_uuid == sid:
        return None

    return (
        f"/private/{app_id}/{match.group('username')}/{controller_uuid}{rest}"
    )


def HandlePrivateURL404s(request):
    redirect_path = _resolve_private_redirect_path(request.path)
    if redirect_path is not None:
        logger.info(
            "Redirecting unresolved private path %s to controller UUID path %s",
            request.path,
            redirect_path,
        )
        return redirect(redirect_path)

    response = HttpResponse("App service not ready.", content_type="text/plain", status=404)
    logger.debug(f"Ambassador app resource may not be mapped to the app service yet. Redirection to app UI happens when it is ready.")
    return response

def index(request):
    # Any additional logic to prepare data for the template can be added here
    # return render(request,'index.html')
    return redirect(to="/helx", permanent=True)

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
