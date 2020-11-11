import logging

from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.sessions.models import Session
from django.http import HttpResponseRedirect
from django.utils.deprecation import MiddlewareMixin

from core.models import AuthorizedUser

logger = logging.getLogger(__name__)
FORMAT = '%(asctime)-15s %(clientip)s %(user)-8s %(message)s'
logging.basicConfig(format=FORMAT)


class AllowWhiteListedUserOnly(MiddlewareMixin):
    def process_request(self, request):
        logger.info(request)
        user = request.user
        logger.info(f"testing user: {user}")
        if user.is_authenticated and not user.is_superuser:
            if not request.path.startswith(settings.LOGIN_URL) \
                    and not request.path.startswith(settings.LOGIN_WHITELIST_URL) \
                    and not request.path.startswith(settings.ADMIN_URL) \
                    and not request.path.startswith(settings.STATIC_URL) \
                    and not request.path.startswith(settings.SAML_URL) \
                    and not request.path.startswith(settings.SAML_ACS_URL):

                if self.is_authorized(user):
                    logger.info(f"Adding user {user} to whitelist")
                    whitelist_group = Group.objects.get(name='whitelisted')
                    user.groups.add(whitelist_group)
                else:
                    logger.info(f"Filtering user {user} is not authorized")
                    self.clear_session(request)
                    return HttpResponseRedirect(settings.LOGIN_WHITELIST_URL)
        logger.info(f"accepting user {user}")
        return None

    @staticmethod
    def is_whitelisted(user):
        if user.groups.filter(name='whitelisted').exists():
            return True
        return False

    @staticmethod
    def is_authorized(user):
        if AuthorizedUser.objects.filter(email=user.email).exists():
            logger.info(f"found user email {user.email} in AuthorizedUser")
            return True
        logger.info(f"user email {user.email} not found in AuthorizedUser")
        return False

    @staticmethod
    def clear_session(request):
        session_key = request.session.session_key
        session = Session.objects.get(session_key=session_key)
        Session.objects.filter(session_key=session).delete()
