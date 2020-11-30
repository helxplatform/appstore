from django.contrib.auth import logout
from django.contrib import messages
import time

from appstore.settings import base

SESSION_IDLE_TIMEOUT =  getattr(base, 'SESSION_IDLE_TIMEOUT', 300)

class SessionIdleTimeout:
    """Middleware class to timeout a session after a specified time period.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, *args, **kwargs):
        if request.user.is_authenticated:
            current_datetime = int(time.time())
            if request.session.has_key('last_activity') and (current_datetime - request.session['last_activity']) > SESSION_IDLE_TIMEOUT:
                messages.info(request, "Session has expired due to prolonged inactivity. Please login to continue.", extra_tags="timeout")
                logout(request)
            else:
                request.session['last_activity'] = current_datetime
        return None
