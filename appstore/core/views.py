import logging
import os
import uuid
from time import sleep

import requests
from django.conf import settings
from allauth.socialaccount.signals import pre_social_login
from django.dispatch import receiver
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.mail import EmailMessage
from django.http import HttpResponseRedirect, HttpResponse
from django.http import JsonResponse
from django.shortcuts import render
from django.views import generic
from irods.access import iRODSAccess
from irods.exception import UserDoesNotExist
from irods.session import iRODSSession
from tycho.context import ContextFactory
from tycho.context import Principal

logger = logging.getLogger(__name__)

"""
Tycho context for application management.
Manages application metadata, discovers and invokes TychoClient, etc.
"""
tycho = ContextFactory.get(
    context_type=settings.TYCHO_MODE,
    product=settings.APPLICATION_BRAND)


@receiver(pre_social_login)
def pre_login(sender, request, sociallogin, **kwargs):
    if sociallogin.token:
        access_token = sociallogin.token
        request.session["Authorization"] = f"Bearer {access_token}"
        logger.debug(f"----------> Adding Bearer token to the user session")


def get_host(request):
    if "HTTP_HOST" in request.META:
        host = request.META["HTTP_HOST"]
    else:
        host = "127.0.0.1"
    return host


def form_service_url(host, app_id, service, username, system=None):
    protocol = os.environ.get('ACCOUNT_DEFAULT_HTTP_PROTOCOL', 'http')
    if service.ip_address:
        url = f"http://{service.ip_address}:{service.port}"
    else:
        url = f"{protocol}://{host}/private/{app_id}/{username}/{system.identifier}/" if system \
            else f"{protocol}://{host}/private/{app_id}/{username}/{service.identifier}/"
    logger.debug(f"-- app-networking constructed url: {url}")
    return url

def principal_params(username):
    social_token_model_objects = ContentType.objects.get(model="socialtoken").model_class().objects.all()
    access_token = None
    refresh_token = None
    for obj in social_token_model_objects:
        if obj.account.user.username == username:
            access_token = obj.token
            refresh_token = obj.token_secret if obj.token_secret else None
            break
        else:
            continue
    return username, access_token, refresh_token

class ApplicationManager(LoginRequiredMixin, generic.TemplateView):
    """ Application manager controller. """
    template_name = 'apps_pods.html'

    def get_context_data(self, *args, **kwargs):
        """
        Query the service manager to determine what services are currently running for this user.
        Create data structures to allow the view to render results.
        """
        context = super(ApplicationManager, self).get_context_data(*args, **kwargs)
        brand = settings.APPLICATION_BRAND
        logger.debug(f"-- running tycho.status() to get running systems.")
        status = tycho.status({
            'username': self.request.user.username
        })
        services = []
        logger.debug(f"-- received {len(status.services)} services in tycho response.")
        for service in status.services:
            name = service.name.split("-")[0]
            lname = name.capitalize()
            app_id = service.app_id.replace(f"-{service.identifier}", "")
            app = tycho.apps.get(app_id, {})
            services.append({
                'app_id': app_id,
                'full_name': service.name,
                'name': form_service_url(get_host(self.request), app_id, service, self.request.user.username),
                'lname': lname,
                'display_name': app.get('name'),
                'logo_name': f'{lname} Logo',
                'logo_path': app.get("icon", "/static/images/app.png"),
                'ip_address': "",
                'port': "",
                'docs': app.get('docs'),
                'identifier': service.identifier,
                'creation_time': service.creation_time,
                'cpu': service.total_util['cpu'],
                'memory': service.total_util['memory']
            })
        brand_map = get_brand_details(brand)
        for app_id, app in tycho.apps.items():
            app['app_id'] = app_id
        apps = sorted(tycho.apps.values(), key=lambda v: v['name'])

        return {
            "brand": brand,
            "logo_url": f"/static/images/{brand}/{brand_map['logo']}",
            "logo_alt": f"{brand_map['name']} Image",
            "svcs_list": services,
            "applications": apps,
        }


class AppStart(LoginRequiredMixin, generic.TemplateView):
    """ Start an application by invoking the app context. """
    template_name = 'starting.html'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        principal = Principal(self.request.user.username)
        app_id = self.request.GET['app_id']
        cpu = str(self.request.GET['cpu'])
        memory = self.request.GET['memory']
        gpu = str(self.request.GET['gpu'])
        resource_request = {
            "deploy": {
                "resources": {
                    "limits": {
                        "cpus": cpu,
                        "memory": memory,
                        "gpus": gpu,
                    },
                    "reservations": {
                        "cpus": cpu,
                        "memory": memory,
                        "gpus": gpu,
                    }
                }
            }
        }
        username = self.request.user.username
        app_id = self.request.GET['app_id']
        if app_id == "dicom-gh":
            params_tup = principal_params(username)
        else:
            params_tup = (username,)
        principal = Principal(*params_tup)
        system = tycho.start(principal, app_id, resource_request)

        return {
            "name": tycho.apps[app_id]['name'],
            "icon": tycho.apps[app_id]['icon'],
            "url": form_service_url(get_host(self.request), app_id, system.services[0], self.request.user.username,
                                    system)
        }


class AppConnect(LoginRequiredMixin, generic.TemplateView):
    """ Show a splash screen while starting the application. """
    template_name = 'starting.html'

    def get_context_data(self, *args, **kwargs):
        """ Return to a running application. """
        return {
            "url": self.request.GET.get("url"),
            "icon": self.request.GET.get("icon"),
            "name": self.request.GET.get("name")
        }


class IrodsLogin(generic.TemplateView):
    template_name = 'irods_login.html'

    def post(self, *args, **kwargs):
        email = self.request.POST.get("irods_email")
        zone = settings.IRODS_ZONE
        collection = settings.IRODS_COLLECTION.split(',')
        context = {'existing_user': 'no'}
        password = str(uuid.uuid4())[:5]
        creds = {'user': os.environ.get('RODS_USERNAME'), 'password': os.environ.get('RODS_PASSWORD'), 'zone': zone}
        with iRODSSession(**creds, host=os.environ.get('BRAINI_RODS'),
                          port=os.environ.get('BRAINI_PORT', "1247")) as session:
            try:
                user = session.users.get(email)
            except UserDoesNotExist:
                context['existing_user'] = 'yes'
                user = session.users.create(email, 'rodsuser')
                with iRODSSession(host=os.environ.get('NRC_MICROSCOPY_IRODS'),
                                  port=os.environ.get('NRC_PORT', "1247"),
                                  **creds) as user_session:

                    user_session.users.modify(user.name, 'password', password)
                    user_session.cleanup()
                message = EmailMessage(
                    'Password Identity',
                    f'Hi {email},\nThis is your existing password  {password} for iRODS login \nThank You',
                    to=[f'{email}']
                )
                message.send()
            session.users.modify(user.name, 'info', user.name)

            for coll in collection:
                coll_obj = session.collections.get(coll)
                access = iRODSAccess('read', coll_obj.path, email, zone)
                session.permissions.set(access, admin=True, recursive=True)
                for i in coll_obj.data_objects:
                    access = iRODSAccess('read', i.path, email, zone)
                    session.permissions.set(access, admin=True)

        return super(generic.TemplateView, self).render_to_response(context)


class ProbeServices(generic.View):
    """ Do a quick network connectivity test on an app endpoint.
    This is a JSON interface hence no class and no template.
    """

    def get(self, *args, **kwargs):
        result = {"status": "fail"}
        try:
            response = requests.get(self.request.GET.get("url"))
            print("Response Request ==>", response)
            # The service is returning a result, regardless of wheher it is nominal
            # or an error, this is not a network failure. Send the redirect.
            # if response.status_code == 404:
            #    sleep(20)
            result = {"status": "ok"}
        except Exception as e:
            logger.info(f"probe services Error  ===> {e}")
            pass  # we're testing connectivity and this URL is failing to connect.
        return JsonResponse(result)


'''
class AppTest(generic.View, LoginRequiredMixin):
    template_name = 'starting.html'

    def get(self, *args, **kwargs):
        """
        Test availability of a running application.
        """
        result = { "status" : "fail" }
        try:
            response = requests.get (self.request.GET.get ("url"))
            # The service is returning a result, regardless of wheher it is nominal
            # or an error, this is not a network failure. Send the redirect.
            result = { "status" : "ok" }
        except requests.exceptions.ConnectionError as e:
            pass # we're testing connectivity and this URL is failing to connect.
        return result
'''


def list_services(request):
    """ Should probably move this to an Ajax JSON request like the probe. """
    if request.method == "POST":
        action = request.POST.get("action")
        sid = request.POST.get("id")
        logger.debug(f"-- action: {action} sid: {sid}")
        if action == "delete":
            logger.debug(f"-- deleting: {sid}")
            response = tycho.delete({"name": sid})
            sleep(2)
            logger.debug(
                f"-- delete response: status: {response}")
    return HttpResponseRedirect("/apps/")


def login_whitelist(request):
    full_brand = get_brand_details(settings.APPLICATION_BRAND)['name']
    logger.debug(f"-- login_whitelist: brand: {settings.APPLICATION_BRAND}, full_brand: {full_brand}")
    return render(request, "whitelist.html", {
        "brand": settings.APPLICATION_BRAND,
        "full_brand": full_brand
    })


def handler404(request, exception, template_name='404.html'):
    if "private" in request.path:
        template_name = "private404.html"
    context = { 'req_path' : request.path }
    response = render(request, template_name, context)
    response.status_code = 404
    return response


def handler500(request, exception=None):
    context = {}
    template_name = "500.html"
    response = render(request, template_name, context)
    response.status_code = 500
    return response


def get_brand_details(brand):
    """
    Any special reason they can't all just be called logo.png?
    (since they're already in namespaced subdirectories)
    Sure would cut down on unproductive complexity here.
    """
    return {
        "braini": {
            "name": "BRAIN-I",
            "logo": "braini-lg-gray.png"
        },
        "scidas": {
            "name": "SciDAS",
            "logo": "scidas-logo-sm.png"
        },
        "catalyst": {
            "name": "BioData Catalyst",
            "logo": "bdc-logo.svg"
        },
        "restartr": {
            "name": "UNC Restarting Research",
            "logo": "restartingresearch.png"
        },
        "commonsshare": {
            "name": "CommonsShare",
            "logo": "logo-lg.png"
        }
    }[brand]

def get_access_token(request):
    access_token = ""
    try:
        auth_string = request.session['Authorization']
        if auth_string and ("Bearer" in auth_string):
            access_token = auth_string.split(" ")[1]
    except Exception as e:
        logger.debug("----------> Failed getting access token. ")
        pass
    return access_token

@login_required
def auth(request):
    """ Provide an endpoint for getting the user identity.
    Supports the use case where a reverse proxy like nginx is being
    used to test authentication of a principal before proxying a request upstream. """
    if request.user and request.user.is_authenticated:
        try:
            response = HttpResponse(content_type="application/json", status=200)
            response["REMOTE_USER"] = request.user
            access_token = get_access_token(request)
            response["ACCESS_TOKEN"] = access_token
            logger.debug(f"----------> remote user and corresponding access token added to the response ----- {response['REMOTE_USER']}")
        except Exception as e:
            response = HttpResponse(content_type="application/json", status=403)
            response["REMOTE_USER"] = request.user
            logger.debug(f"----------> exception with the remote user ----- {request.user}")
    else:
        response = HttpResponse(content_type="application/json", status=403)
        response["REMOTE_USER"] = request.user
        logger.debug(f"----------> user is not authenticated on the server ----- {request.user}")
    return response
