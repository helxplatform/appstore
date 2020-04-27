from django.http import HttpResponseRedirect
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

import logging
#logger = logging.getLogger (__name__)
#FORMAT = '%(asctime)-15s %(clientip)s %(user)-8s %(message)s'
#logging.basicConfig(format=FORMAT)

class AllowWhiteListedUserOnly(MiddlewareMixin):
    def process_request(self, request):
        user = request.user
        #logger.info (f"testing user: {user}")
        print(f"testing user: {user}")

        if user.is_authenticated and not user.is_superuser:
            if not request.path.startswith(settings.LOGIN_URL) \
                    and not request.path.startswith(settings.ADMIN_URL) \
                    and not request.path.startswith(settings.STATIC_URL):
                if not user.groups.filter(name='whitelisted').exists():
                    #logger.info (f"user groups for user {user}: {user.groups}")
                    #logger.info (f"Filtering user {user} is not whitelisted")
                    print (f"user groups for user {user}: {user.groups}")
                    print (f"Filtering user {user} is not whitelisted")
                    return HttpResponseRedirect(settings.LOGIN_URL)
        #logger.info (f"accepting user {user}")
        print(f"accepting user {user}")
        return None