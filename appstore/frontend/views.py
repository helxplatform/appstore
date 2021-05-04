from functools import lru_cache

from allauth.account.views import LoginView

from api.v1.views import AppContextViewSet

from django.http import HttpRequest
from django.urls import reverse_lazy
from django.views.generic.base import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

from rest_framework.test import APIRequestFactory

import requests

"""
#######
Summary
#######

The new appstore frontend project can be found at https://github.com/helxplatform/helx-ui.

Along with handling all of the user based appstore interactions post authentication
the frontend project builds and packages it's own artifacts which appstore consumes
via a docker multistage build.

This django app/view is responsible for authenticating the user and 
serving the frontend assets.

#############
Configuration
#############

Serving of the frontend has been setup to understand as little as possible about
[helx-ui](https://github.com/helxplatform/helx-ui) as long as the following
criteria is met a frontend will be rendered after auth.

* The frontend will provide `index.html` which will be placed in `frontend/templates`
during the appstore build.
* The frontend assets will be available at `./frontend/static/frontend` so that it is
collected by the `collectstatic` step and put into a `frontend` directory in
the static root.

.. note::
**The frontend should load assets from this path**.

###
Dev
###

For local development you can run `bin/appstore image frontend` which will
provide the frontend resources to your local development environment. Following
that with `bin/appstore start {brand}` will then run `collectstatic` and database
migrations finishing local appstore setup.

#####
Build
#####

For deployments the frontend artifacts are managed with a multistage build. In
`Dockerfile` we pull the frontend image and then copy the webpack artifacts to
`frontend/static` which will then be picked up with the `CMD` step at container
start.
"""


@lru_cache(maxsize=5, typed=False)
def get_brand_details():
    view = AppContextViewSet
    factory = APIRequestFactory()
    list_view = view.as_view({"get": "list"})
    response = list_view(factory.get(""))
    return response.data


class HelxLoginView(LoginView):
    """
    Provides the login landing page data based on allauth, customized for HeLx.
    """

    template_name = "frontend/landing.html"
    success_url = reverse_lazy("helx")
    redirect_field_name = "next"
    brand_context = get_brand_details()
    brand = brand_context["brand"]
    brand_logo = brand_context["logo_url"]
    brand_title = brand_context["title"]
    brand_color_scheme = brand_context["color_scheme"]
    brand_links = brand_context["links"]

    def get_context_data(self, **kwargs):
        context = super(HelxLoginView, self).get_context_data(**kwargs)
        context["brand"] = self.brand
        context["brand_logo"] = self.brand_logo
        context["brand_title"] = self.brand_title
        context["brand_links"] = self.brand_links
        context["redirect_field_name"] = self.redirect_field_name
        context["redirect_field_value"] = self.success_url
        return context

    def get(self, request, *args, **kwargs):
        request.session["helx_frontend"] = "react"
        if request.user.is_authenticated:
            return redirect(success_url)
        return super(LoginView, self).get(request, *args, **kwargs)


class HelxSpaLoaderView(TemplateView):
    """
    Serve frontend artifact after authentication.
    """

    template_name = "frontend/index.html"

    @method_decorator(login_required(login_url=reverse_lazy("helx_login")))
    def dispatch(self, *args, **kwargs):
        return super(HelxSpaLoaderView, self).dispatch(*args, **kwargs)