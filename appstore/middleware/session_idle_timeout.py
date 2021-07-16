from django.contrib.auth import logout
from django.contrib import messages
from django.utils.http import urlencode
import logging
import time
import requests

from appstore.settings import base

SESSION_IDLE_TIMEOUT =  getattr(base, 'SESSION_IDLE_TIMEOUT', 300)

logger = logging.getLogger(__name__)

class SessionIdleTimeout:
    """Middleware class to timeout a session after a specified time period.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def oidc_logout(self,request):
       logout_url = base.OIDC_OP_LOGOUT_ENDPOINT
       logger.info("meta items:")
       for k,v in request.META.items(): 
           logger.info("META k,v = " + str(k) + " " + str(v))
       logger.info("session items:")
       for k,v in request.session.items():
           logger.info("SESSION k,v = " + str(k) + " " + str(v))
       logger.info("user items:")
       for k,v in request.user.items():
           logger.info("USER k,v = " + str(k) + " " + str(v))
       logger.info("request = " + str(request))
       logger.info("oidc logout to " + logout_url)
       requests.get(logout_url,params={ 'client_id':base.OIDC_RP_CLIENT_ID})

    def process_view(self, request, view_func, *args, **kwargs):
        if request.user.is_authenticated:
            current_datetime = int(time.time())
            if request.session.has_key('last_activity') and (current_datetime - request.session['last_activity']) > SESSION_IDLE_TIMEOUT:
                messages.info(request, "Session has expired due to prolonged inactivity. Please login to continue.", extra_tags="timeout")
                logger.info("session logout")
                self.oidc_logout(request)
                logout(request)
            else:
                request.session['last_activity'] = current_datetime
        return None
