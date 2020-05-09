import json
import logging
import requests
from apps_core_services.get_pods import get_pods_services, delete_pods
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.views import generic
from time import sleep
from tycho.context import Principal
from tycho.context import ContextFactory

logger = logging.getLogger(__name__)

"""
Tycho context for application management.
Manages application metadata, discovers and invokes TychoClient, etc.
"""
tycho = ContextFactory.get (
    context_type=settings.TYCHO_MODE,
    product=settings.APPLICATION_BRAND)

def form_service_url (app_id, service, username):
    logger.debug (f"--- service: {service} --- username: {username}")
    url = None
    logger.debug ("-- ip address: {service.ip_address}")
    if service.ip_address:
        """ If there's an ip address and port, go there. This is a dev only scenario. """
        url = f"http://{service.ip_address}:{service.port}"
    else:
        """ Otherwise build a URL assuming a reverse proxy is configured. """
        url = f"/private/{app_id}/{username}/{service.identifier}/"
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
        logger.debug (f"-- running tycho.status() to get running systems.")
        status = tycho.status ({
            'username' : self.request.user.username
        })
        services = []
        logger.debug (f"-- received {len(status.services)} services in tycho response.")
        for service in status.services:
            name = service.name.split("-")[0]
            lname = name.capitalize()
            app_id = service.name.replace (f"-{service.identifier}", "")
            app_icon = tycho.apps.get (app_id, {}).get("icon", "unknown-icon")
            services.append({
                'app_id'        : app_id,
                'full_name'     : service.name,                
                'name'          : form_service_url (app_id, service, self.request.user.username),
                'lname'         : lname,
                'display_name'  : tycho.apps[app_id]['name'],
                'logo_name'     : f'{lname} Logo',
                'logo_path'     : app_icon,
                'ip_address'    : "",
                'port'          : "",
                'docs'          : tycho.apps[app_id]['docs'],
                'identifier'    : service.identifier,
                'creation_time' : service.creation_time,
                'cpu'           : service.total_util['cpu'],
                'memory'        : service.total_util['memory']
            })
        brand_map = get_brand_details (brand)
        for app_id, app in tycho.apps.items ():
            app['app_id'] = app_id
            #logger.debug (f"-- app: {json.dumps(app, indent=2)}")
        apps = sorted(tycho.apps.values (), key=lambda v: v['name'])
        return {
            "brand"        : brand, #brand_map['name'],
            "logo_url"     : f"/static/images/{brand}/{brand_map['logo']}",
            "logo_alt"     : f"{brand_map['name']} Image",
            "svcs_list"    : services,
            "applications" : apps
        }
    
class AppStart(generic.TemplateView, LoginRequiredMixin):

    """ Application manager controller. """
    template_name = 'starting.html'
    
    def get_context_data(self, *args, **kwargs):
        """
        Start an application.
        """
        principal = Principal (self.request.user.username)
        app_id = self.request.GET['app_id']
        system = tycho.start (principal, app_id)
        return {
            "name" : tycho.apps[app_id]['name'],
            "icon" : tycho.apps[app_id]['icon'],
            "url"  : form_service_url (app_id, system.services[0], self.request.user.username)
        }

class AppConnect(generic.TemplateView, LoginRequiredMixin):

    """ Application manager controller. """
    template_name = 'starting.html'
    
    def get_context_data(self, *args, **kwargs):
        """ Return to a running application. """
        return {
            "url"  : self.request.GET.get ("url"),
            "icon" : self.request.GET.get ("icon"),
            "name" : self.request.GET.get ("name")
        }

from django.http import JsonResponse
def probe_service (request):    
    """
    Test availability of a running application.
    """
    result = { "status" : "fail" }
    try:
        response = requests.get (request.GET.get ("url"))
        # The service is returning a result, regardless of wheher it is nominal
        # or an error, this is not a network failure. Send the redirect.
        result = { "status" : "ok" }
    except requests.exceptions.ConnectionError as e:
        pass # we're testing connectivity and this URL is failing to connect.
    return JsonResponse(result)
    
class AppTest(generic.View, LoginRequiredMixin):

    """ Application manager controller. """
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
    
def list_services(request):
    if request.method == "POST":
        action = request.POST.get("action")
        sid = request.POST.get("id")
        logger.debug (f"-- action: {action} sid: {sid}")
        if action == "delete":
            logger.debug (f"-- deleting: {sid}")
            response = tycho.delete ({ "name" : sid })
            sleep(2)
            logger.debug (
                f"-- delete response: status: {response}")
    return HttpResponseRedirect("/apps/")

def login_whitelist(request):
    full_brand = get_brand_details (settings.APPLICATION_BRAND)['name']
    logger.debug (f"-- login_whitelist: brand: {brand}, full_brand: {full_brand}")
    return render(request, "whitelist.html", {
        "brand"      : brand,
        "full_brand" : full_brand
    })

def get_brand_details (brand):
    """
    Any special reason they can't all just be called logo.png?
    (since they're already in namespaced subdirectories)
    Sure would cut down on unproductive complexity here.
    """
    return {
        "braini"       : {
            "name" : "BRAIN-I",
            "logo" : "braini-lg-gray.png"
        },
        "scidas"       : {
            "name" : "SciDAS",
            "logo" : "scidas-logo-sm.png"
        },
        "catalyst"     : {
            "name" : "BioData Catalyst",
            "logo" : "bdc-logo.svg"
        },
        "commonsshare" : {
            "name" : "CommonsShare",
            "logo" : "logo-lg.png"
        }
    }[brand]

def auth(request):
    if request.user:
        try:
            response = HttpResponse(content_type="application/json", status=200)
            response["REMOTE_USER"] = request.user
            logger.debug (f"{response['REMOTE_USER']}")
        except Exception as e:
            response = HttpResponse(content_type="application/json", status=403)
            response["REMOTE_USER"] = request.user
    else:
        response = HttpResponse(content_type="application/json", status=403)
        response["REMOTE_USER"] = request.user
    return response
