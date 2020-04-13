from django.conf import settings
from django.http import HttpResponseRedirect, HttpResponseBadRequest

from apps_core_services.utils import check_authorization, authenticate_user

# Create your views here.


def phenotype_analyze(request):
    token = request.GET.get('access_token', None)
    uname = request.GET.get('user_name', None)
    uemail = request.GET.get('email', None)
    if not token or not uname:
        auth_resp = check_authorization(request)
        if auth_resp.status_code != 200:
            return HttpResponseRedirect("/")
        else:
            return HttpResponseRedirect(settings.PHENOTYPE_REDIRECT_URL)
    else:
        # requests coming from auth service return which already authenticated the user
        name = request.GET.get('name', None)
        ret_user = authenticate_user(request, username=uname, access_token=token,
                                     name=name, email=uemail)
        if ret_user:
            return HttpResponseRedirect(settings.PHENOTYPE_REDIRECT_URL)
        else:
            return HttpResponseBadRequest(
                'Bad request - no valid access_token or user_name is provided')
