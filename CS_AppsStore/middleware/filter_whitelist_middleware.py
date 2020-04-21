from django.http import HttpResponseRedirect
from django.conf import settings
import os

from django.utils.deprecation import MiddlewareMixin


class AllowWhiteListedUserOnly(MiddlewareMixin):
    def process_request(self, request):
        user = request.user
        print(user)

        if user.is_authenticated:
            if not request.path.startswith(settings.LOGIN_URL) and not request.path.startswith(settings.ADMIN_URL):
                if not user.groups.filter(name='whitelisted').exists():
                    print("Filtering user - not whitelisted")
                    return HttpResponseRedirect(settings.LOGIN_URL)
                else:
                    print("Letting user in - whitelisted")
        return None