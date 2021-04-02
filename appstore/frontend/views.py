from allauth.account.views import LoginView

from django.urls import reverse_lazy
from django.views.generic.base import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin


"""
#######
Summary
#######

The new appstore frontend project can be found at https://github.com/helxplatform/helx-ui.

Along with handling all of the user based appstore interactions the frontend
project also builds and packages it's own artifacts which appstore makes use 
of via a docker multistage build.

This django app/view is responsible for serving those assets.

#############
Configuration
#############

Serving of the frontend has been setup to understand as little as possible about
the technology and build steps used in [helx-ui](https://github.com/helxplatform/helx-ui).

The assumptions that have been configured are:

- The frontend will provide an `index.html` which can be referenced by `FrontendView`
as a template.
- The frontend will be available at `./frontend/static/frontend` so that it is
collected by the `collectstatic` step and put into a `frontend` directory in
the static root.

If those two things are true we will serve the frontend with the use of
`collectstatic`, the routes configured in `appstore/urls.py` (`frontend` and 
`static`), and `FrontendView` treating `static/frontend/index.html` as a
template.

Template look up configuration is setup in `appstore/settings/base.py` where
`static` is included in `TEMPLATES["DIRS"]`. The frontend app namespaces its
contents in `static/frontend` and `FrontendView` contains a namespace for the
`index.html` file to prevent collisions with other index templates or static
artifacts. 

#########
Dev/Build
#########

For local development you can run `bin/appstore image frontend` which will
provide the frontend resources to your local development environment. Following
that with `bin/appstore start {brand}` will then run `collectstatic` and database
migrations finishing local appstore setup.

For deployments the frontend artifacts are managed with a multistage build. In
`Dockerfile` we pull the frontend image and then copy the webpack artifacts to
`frontend/static` which will then be picked up with the `CMD` step at container
start.
"""


class FrontendView(LoginView):
    """
    Homepage view.

    Provides the login form based on allauth package.

    Upon successful auth serves up the react app.
    """

    template_name = "frontend/landing.html"
    success_url = reverse_lazy("frontend-react")
    redirect_field_name = "next"

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(success_url)
        return super(LoginView, self).get(request, *args, **kwargs)


class ReactView(LoginRequiredMixin, TemplateView):
    """
    Serves up the react app.
    """

    template_name = "frontend/index.html"
