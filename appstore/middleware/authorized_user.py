import logging

from smtplib import SMTPSenderRefused, SMTPResponseException

from django.conf import settings
from django.http import HttpResponseForbidden
from django.contrib.auth.models import Group
from django.contrib.sessions.models import Session

from core.models import AuthorizedUser

logger = logging.getLogger(__name__)
FORMAT = "%(asctime)-15s %(clientip)s %(user)-8s %(message)s"
logging.basicConfig(format=FORMAT)


class AuthorizedUserCheck:
    """
    Along with being logged in a user must be authorized via a whitelist to use
    the helx appstore. If a user is not part of the whitelist group then they
    should receive a PermissionDenied HTTP Response.

    The following tables are used to check if a user is authorized:

    core_authorizeduser - checks if user email is authorized by an admin
    auth_user_groups - maps the user to the whitelist group, but unused
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        logger.info(f"Checking if {user} is authorized.")

        if user.is_authenticated and not (
            user.is_superuser or self.is_public_path(request.path)
        ):
            if not self.is_authorized(user):
                logger.info(f"User {user} is not authorized")
                try:
                    # This will fail if email isn't setup correctly and won't
                    # route the user correctly.
                    self.send_whitelist_email(request, user)
                except (SMTPSenderRefused, SMTPResponseException) as err:
                    logger.error(f"SMTP misconfigured, please check settings.\n{err}\n")
                finally:
                    # Make sure to always return Forbidden in this condition path.
                    self.clear_session(request)
                    return HttpResponseForbidden()

        response = self.get_response(request)
        return response

    def is_public_path(self, url):
        """
        Some resources need to be available without a user being logged in, or
        authorized.
        """
        public = any(
            [
                url.startswith(settings.LOGIN_URL),
                url.startswith(settings.LOGIN_WHITELIST_URL),
                url.startswith(settings.ADMIN_URL),
                url.startswith(settings.STATIC_URL),
                url.startswith(settings.SAML_URL),
                url.startswith(settings.SAML_ACS_URL),
                url.startswith(settings.APP_CONTEXT_URL),
                url.startswith(settings.APP_LOGIN_PROVIDER_URL),
            ]
        )
        logger.info(f"Checking if access path {url} is public: {public}")
        return public

    def is_authorized(self, user):
        if AuthorizedUser.objects.filter(email=user.email).exists():
            logger.info(f"found user email {user.email} in AuthorizedUser")
            return True
        logger.info(f"user email {user.email} not found in AuthorizedUser")
        return False

    def clear_session(self, request):
        session_key = request.session.session_key
        session = Session.objects.get(session_key=session_key)
        Session.objects.filter(session_key=session).delete()

    def send_whitelist_email(self, request, user):
        """
        For users that are able to login but are not authorized to use appstore
        yet send an email to the admins to authorize the user.

        This will fail if SMTP is not configured correctly.
        """
        msg = (
            f"A user {user.email} is requesting access to AppStore on {settings.APPLICATION_BRAND} "
            f"and needs to be reviewed for whitelisting. Upon successful review, kindly "
            f"add the user to Authorized Users using django admin panel at "
            f"{request.scheme}://{request.META.get('SERVER_NAME')}{settings.ADMIN_URL}"
        )

        logger.info(f"Sending email:\n{msg}")

        send_mail(
            "Whitelisting Required",
            msg,
            settings.EMAIL_HOST_USER,
            [settings.APPLICATION_BRAND + "-admin@lists.renci.org"],
            fail_silently=False,
        )