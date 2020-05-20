import logging
from time import sleep

import irods.test.helpers as helpers
import requests
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect, HttpResponse
from django.http import JsonResponse
from django.shortcuts import render
from django.views import generic
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


def form_service_url(app_id, service, username):
    url = f"http://{service.ip_address}:{service.port}" if service.ip_address \
        else f"/private/{app_id}/{username}/{service.identifier}/"
    logger.debug(f"-- app-networking constructed url: {url}")
    return url


class ApplicationManager(generic.TemplateView, LoginRequiredMixin):
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
                'name': form_service_url(app_id, service, self.request.user.username),
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
            "applications": apps
        }


class AppStart(generic.TemplateView, LoginRequiredMixin):
    """ Start an application by invoking the app context. """
    template_name = 'starting.html'

    def get_context_data(self, *args, **kwargs):
        principal = Principal(self.request.user.username)
        app_id = self.request.GET['app_id']
        system = tycho.start(principal, app_id)
        return {
            "name": tycho.apps[app_id]['name'],
            "icon": tycho.apps[app_id]['icon'],
            "url": form_service_url(app_id, system.services[0], self.request.user.username)
        }


class AppConnect(generic.TemplateView, LoginRequiredMixin):
    """ Show a splash screen while starting the application. """
    template_name = 'starting.html'

    def get_context_data(self, *args, **kwargs):
        """ Return to a running application. """
        return {
            "url": self.request.GET.get("url"),
            "icon": self.request.GET.get("icon"),
            "name": self.request.GET.get("name")
        }


# class IrodsLogin(generic.TemplateView):
#     template_name = 'irods_login.html'
#
#     def get(self, *args, **kwargs):
#         #session = helpers.make_session()
#         #user = session.users.get('aniroo94')
#         #print("===>" ,session.query(user.name).first())
#         return render(self.request, self.template_name)
#
#     def post(self, *args, **kwargs):
#         print(self.request.POST.get("irods_email"))
#         return render(self.request, self.template_name)


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
        "commonsshare": {
            "name": "CommonsShare",
            "logo": "logo-lg.png"
        }
    }[brand]


def auth(request):
    """ Provide an endpoint for getting the user identity.
    Supports the use case where a reverse proxy like nginx is being
    used to test authentication of a principal before proxying a request upstream. """
    if request.user:
        try:
            response = HttpResponse(content_type="application/json", status=200)
            response["REMOTE_USER"] = request.user
            logger.debug(f"{response['REMOTE_USER']}")
        except Exception as e:
            response = HttpResponse(content_type="application/json", status=403)
            response["REMOTE_USER"] = request.user
    else:
        response = HttpResponse(content_type="application/json", status=403)
        response["REMOTE_USER"] = request.user
    return response
