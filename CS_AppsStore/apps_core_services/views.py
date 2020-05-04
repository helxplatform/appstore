import logging
from time import sleep

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.views import generic

from apps_core_services.get_pods import get_pods_services, delete_pods

logger = logging.getLogger(__name__)


class ApplicationManager(generic.TemplateView, LoginRequiredMixin):
    template_name = 'apps_pods.html'

    def get_context_data(self, *args, **kwargs):
        context = super(ApplicationManager, self).get_context_data(*args, **kwargs)
        logger.debug("Working in Application Manager")
        tycho_status = get_pods_services(self.request.user.username)
        services = tycho_status.services
        svcs_list = []
        path_prefix = "/static/images/"
        path_suffix = "-logo.png"
        for service in services:
            full_name = service.name
            name = service.name.split("-")[0]
            lname = name.capitalize()
            logo_name = f'{lname} Logo'
            logo_path = f'{path_prefix}{name}{path_suffix}'
            ip_address = service.ip_address
            if (ip_address == 'x'):
                ip_address = '--'
            port = service.port
            if port == '':
                port = '--'
            identifier = service.identifier
            creation_time = service.creation_time

            svcs_list.append({'full_name': full_name,
                              'name': name,
                              'lname': lname,
                              'logo_name': logo_name,
                              'logo_path': logo_path,
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
        logo_prefix = "/static/images/" + brand + "/"
        logo_url = logo_prefix + fnames[brand]
        if brand == "braini":
            full_brand = "Brain-I"
        elif brand == "scidas":
            full_brand = "SciDAS"
        elif brand == "catalyst":
            full_brand = "Biodata Catalyst"
        else:
            full_brand = "CommonsShare"

        logo_alt = full_brand + " Image"
        context['brand'] = brand
        context['logo_url'] = logo_url
        context['logo_alt'] = logo_alt
        context['svcs_list'] = svcs_list
        return context


def list_services(request):
    if request.method == "POST":
        action = request.POST.get("action")
        sid = request.POST.get("id")
        print(f"ACTION: {action}, SID: {sid}")
        if action == "delete":
            delete_pods(request, sid)
            sleep(2)
            return HttpResponseRedirect("/apps/")
    else:
        return HttpResponseRedirect("/apps/")


@login_required
def login_whitelist(request):
    print("LOGIN_WHITELIST: Rendering whitelist.html")
    brand = settings.APPLICATION_BRAND
    if brand == "braini":
        full_brand = "Brain-I"
    elif brand == "scidas":
        full_brand = "SciDAS"
    elif brand == "catalyst":
        full_brand = "Biodata Catalyst"
    else:
        full_brand = "CommonsShare"

    print(f"BRAND: {brand}, FULL_BRAND: {full_brand}")
    return render(request, "whitelist.html", {"brand": brand, "full_brand": full_brand})
