from django.shortcuts import render
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import HttpResponseRedirect, HttpResponseBadRequest, HttpResponse
from django.apps import apps
import json
import xml.etree.ElementTree as ET

from apps_core_services.utils import check_authorization, authenticate_user

from allauth.socialaccount.providers.github.views import GitHubOAuth2Adapter
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from rest_auth.registration.views import SocialLoginView

from apps_core_services.get_pods import get_pods_services, delete_pods
from time import sleep

# Create your views here.

class GithubLogin(SocialLoginView):
    adapter_class = GitHubOAuth2Adapter
    callback_url = "http://127.0.0.1:8000/accounts/github/login/callback/"
    client_class = OAuth2Client

class GoogleLogin(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter
    client_class = OAuth2Client
    callback_url = "http://127.0.0.1:8000/accounts/google/login/callback/"

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated


class AppsStore_JWT(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        content = {'message': 'Testing AppsStore JWT Token Creation!'}
        return Response(content)

def home_page_view(request):
    auth_resp = check_authorization(request)
    if auth_resp.status_code != 200:
        return auth_resp
    return render(request, "apps.html", {})


def signout_view(request):
    #print(request)
    #print(request.GET['token'])
    #print(request.GET['session_id'])
    #del  request.GET['token']
    #del request.GET['session_id']
    #logout(request)
    return redirect('/accounts/logout/')


@login_required
def login_show_apps(request):
    print(f"~~~~~REQUEST: {request.GET}, {request.META}")
    try:
       print(f"REQUEST USER: {request.user.username}, {request.user.email}")
       request.META['REMOTE_USER'] = request.user.username
    except Exception as e:
       print("Failed to get request.META['REMOTE_USER']")
       pass

    tycho_status = get_pods_services(request)
    print(f"login_show_apps: TYCHO STATUS: {tycho_status}")
    services = tycho_status.services
    print(f"TYCHO SERVICES: {services}")

    svcs_list = []
    path_prefix = "/static/images/"
    path_suffix = "-logo.png"
    print("Listing services")
    for service in services:
        full_name = service.name
        print(f"Found service: {full_name}")
        name = service.name.split("-")[0]
        lname = name.capitalize()
        logo_name = f'{lname} Logo'
        logo_path = f'{path_prefix}{name}{path_suffix}'
        ip_address = service.ip_address
        if(ip_address == 'x'):
            ip_address = '--'
        port = ''
        port = service.port
        if port == '':
            port = '--'
        identifier = service.identifier
        creation_time =  service.creation_time

        print("APP VALUES:")
        print(f"FULL_NAME: {full_name}")
        print(f"NAME: {name}")
        print(f"LNAME: {lname}")
        print(f"LOGO_NAME: {logo_name}")
        print(f"LOGO_PATH: {logo_path}")
        print(f"IP_ADDRESS: {ip_address}")
        print(f"PORT: {port}")
        print(f"IDENTIFIER: {identifier}")
        print(f"CREATION_TIME: {creation_time}")
        print(" ")

        svcs_list.append({'full_name': full_name,
                          'name': name,
                          'lname': lname,
                          'logo_name': logo_name,
                          'logo_path':logo_path,
                          'ip_address': ip_address,
                          'port': port,
                          'identifier': identifier,
                          'creation_time': creation_time})

    # Get main logo url and alt vars
    fnames = {"braini": "braini-lg-gray.png",
              "scidas": "scidas-logo-sm.png",
              "catalyst": "bdc-logo.svg",
              "commonsshare": "logo-lg.png"}

    brand = settings.APPLICATION_BRAND
    print(f"BRAND: {brand}")
    logo_prefix = "/static/images/" + brand + "/"
    logo_url = logo_prefix + fnames[brand]
    print(f"LOGO_URL: {logo_url}")
    logo_alt = brand + " image"
    return render(request, "apps_pods.html", {"brand": brand, "logo_url": logo_url, "logo_alt": logo_alt, "svcs_list": svcs_list})


def show_apps(request):
    token = request.GET.get('access_token', None)
    uname = request.GET.get('user_name', None)
    uemail = request.GET.get('email', None)

    if not token or not uname:
        auth_resp = check_authorization(request)
        if auth_resp.status_code != 200:
            return HttpResponseRedirect("/")
        else:
            return HttpResponseRedirect("/login_apps/")
    else:
        # requests coming from auth service return which already authenticated the user
        name = request.GET.get('name', None)
        ret_user = authenticate_user(request, username=uname, access_token=token,
                                name=name, email=uemail)
        if ret_user:
            return HttpResponseRedirect("/login_apps/")
        else:
            return HttpResponseBadRequest(
                'Bad request - no valid access_token or user_name is provided')


@login_required
def list_services(request):
    # list_pods url comes here . . .
    path_prefix = "/static/images/"
    path_suffix = "-logo.png"
    if request.method == "POST":
        action = request.POST.get("action")
        sid = request.POST.get("id")
        print(f"ACTION: {action}, SID: {sid}")
        if action == "delete":
            delete_pods(request, sid)
            sleep(2)
            return HttpResponseRedirect("/login_apps/")
    else:
        return HttpResponseRedirect("/login_apps/")


def auth(request):
    if request.user:
        try:
            response = HttpResponse(content_type="application/json", status=200)
            response["REMOTE_USER"] = request.user
            print(f"{response['REMOTE_USER']}")
        except Exception as e:
            response = HttpResponse(content_type="application/json", status=403)
            response["REMOTE_USER"] = request.user
    else:
        response = HttpResponse(content_type="application/json", status=403)
        response["REMOTE_USER"] = request.user
    return response



def test(request):
    print(f"========= Request sent from nginx =========")
    for item in request.META:
        print(f"{item}: {request.META[item]}")
    response = HttpResponse(content_type="application/json", status=200)
    return response
