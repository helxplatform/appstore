import logging
import re

from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.sessions.models import Session
from django.http import HttpResponseRedirect
from django.utils.deprecation import MiddlewareMixin
from django.core.mail import send_mail

from smtplib import SMTPSenderRefused, SMTPResponseException

from core.models import AuthorizedUser

logger = logging.getLogger(__name__)
FORMAT = "%(asctime)-15s %(clientip)s %(user)-8s %(message)s"
logging.basicConfig(format=FORMAT)


class AllowWhiteListedUserOnly(MiddlewareMixin):
    def __init__(self, get_response=None):
        if get_response is not None:
            self.get_response = get_response
        else:
            self.get_response = self._get_response

    def process_request(self, request):
        user = request.user
        logger.debug(f"testing user: {user}")

        if user.is_authenticated and not user.is_superuser:
            if not any(
                [
                    request.path.startswith(settings.LOGIN_URL),
                    request.path.startswith(settings.LOGIN_WHITELIST_URL),
                    request.path.startswith(settings.ADMIN_URL),
                    request.path.startswith(settings.STATIC_URL),
                    request.path.startswith(settings.SAML_URL),
                    request.path.startswith(settings.SAML_ACS_URL),
                    request.path.startswith("/api/v1/context"),
                    request.path.startswith("/api/v1/providers"),
                ]
            ):
                if self.is_authorized(user):
                    logger.debug(f"Adding user {user} to whitelist")
                    whitelist_group = Group.objects.get(name="whitelisted")
                    user.groups.add(whitelist_group)
                else:
                    logger.debug(f"Filtering user {user} is not authorized")
                    self.clear_session(request)
                    try:
                        # This will fail if email isn't setup correctly and won't
                        # route the user correctly.
                        self.send_whitelist_email(request, user)
                    except (SMTPSenderRefused, SMTPResponseException) as err:
                        logger.error(
                            f"SMTP misconfigured, please check settings.\n{err}\n"
                        )
                    finally:
                        # Make sure to always run the redirect.
                        return HttpResponseRedirect(settings.LOGIN_WHITELIST_URL) 
        return None

    def _get_response(self, request):
        """
        Call the next middleware in the chain to get a response.
        """
        # Call the next middleware in the chain to get a response
        if hasattr(self, 'process_response'):
            return self.process_response(request)
        else:
            # If there's no process_response method, return None
            return None

    @staticmethod
    def is_whitelisted(user):
        if user.groups.filter(name="whitelisted").exists():
            return True
        return False
    
    @staticmethod
    def is_auto_whitelisted_email(user):
        email = user.email
        for pattern in settings.AUTO_WHITELIST_PATTERNS:
            if re.match(pattern, email) is not None:
                return True
        return False
    
    @staticmethod
    def is_whitelisted_username(user):
        username = user.username
        

    @staticmethod
    def is_authorized(user):
        if AuthorizedUser.objects.filter(email=user.email).exists():
            logger.debug(f"found user email {user.email} in AuthorizedUser")
            return True
        if AllowWhiteListedUserOnly.is_auto_whitelisted_email(user):
            # authorize the user automatically, and allow them through.
            AuthorizedUser.objects.create(email=user.email)
            return True
        if AuthorizedUser.objects.filter(username=user.username).exists():
            logger.debug(f"found user with username {user.username} in AuthorizedUser")
            return True
        logger.debug(f"user email {user.email} not found in AuthorizedUser")
        return False

    @staticmethod
    def clear_session(request):
        session_key = request.session.session_key
        session = Session.objects.get(session_key=session_key)
        Session.objects.filter(session_key=session).delete()

    @staticmethod
    def send_whitelist_email(request, user):
        logger.debug("sending email")

        recipient_list_string = settings.RECIPIENT_EMAILS
        recipient_list = recipient_list_string.split(",")

        msg = (
            "A user "
            + user.email
            + "/"
            + user.username
            + " is requesting access to AppStore on "
            + settings.APPLICATION_BRAND
            + " and needs to be reviewed for whitelisting. Upon successful review, kindly add the user to"
            + " Authorized Users using django admin panel at "
            + request.scheme
            + "://"
            + request.META["HTTP_HOST"]
            + settings.ADMIN_URL
            + "."
        )
        logger.debug(msg)

        send_mail(
            "Whitelisting Required",
            msg,
            settings.EMAIL_HOST_USER,
            recipient_list,
            fail_silently=False,
        )
