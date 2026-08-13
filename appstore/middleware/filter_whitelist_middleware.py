import os
import logging
import re
from functools import lru_cache

from django.conf import settings
from django.contrib.auth.models import Group
from django.http import HttpResponseRedirect
from django.utils.deprecation import MiddlewareMixin
from django.core.mail import send_mail
from smtplib import SMTPSenderRefused, SMTPResponseException

from ldap3 import Server, Connection, SUBTREE  # NEW
from core.models import AuthorizedUser


logger = logging.getLogger(__name__)
FORMAT = "%(asctime)-15s %(clientip)s %(user)-8s %(message)s"
logging.basicConfig(format=FORMAT)


class AllowWhiteListedUserOnly(MiddlewareMixin):

    @staticmethod
    @lru_cache(maxsize=1)
    def _ldap_conn():
        """One connection per worker, with DEBUG breadcrumbs."""
        uri = os.getenv("LDAP_URI")
        if not uri:
            logger.debug("[LDAP] LDAP_URI not set → LDAP feature disabled")
            return None

        bind_dn = os.getenv("LDAP_BIND_DN", "")
        bind_pw = os.getenv("LDAP_BIND_PASSWORD", "")

        logger.debug("[LDAP] Connecting to %s (bind_dn=%s)", uri, bind_dn or "anonymous")
        try:
            server = Server(uri, get_info=None)
            conn   = Connection(server, user=bind_dn, password=bind_pw, auto_bind=True)
            logger.debug("[LDAP] Connection established. Server info: %s", server)
            return conn
        except Exception as exc:                               # noqa: BLE001
            logger.error("[LDAP] Connection failed: %s", exc)
            return None

    @classmethod
    def _ldap_group_member(cls, user):
        """Return True when user is in LDAP_GROUP_DN; log every step."""
        conn     = cls._ldap_conn()
        group_dn = os.getenv("LDAP_GROUP_DN")
        if not conn:
            logger.debug("[LDAP] No connection – skipping LDAP checks")
            return False
        if not group_dn:
            logger.debug("[LDAP] LDAP_GROUP_DN unset – skipping LDAP checks")
            return False

        base   = os.getenv("LDAP_SEARCH_BASE", group_dn.split(",", 1)[1])
        flt    = f"(|(mail={user.email})(uid={user.username}))"
        logger.debug("[LDAP] Searching base=%s filter=%s", base, flt)

        try:
            ok = conn.search(base, flt, SUBTREE, attributes=[])
            logger.debug("[LDAP] Search ok=%s; hits=%s", ok, len(conn.entries))
            if not ok or not conn.entries:
                return False
            user_dn = conn.entries[0].entry_dn
            logger.debug("[LDAP] Resolved user_dn=%s", user_dn)
        except Exception as exc:                               # noqa: BLE001
            logger.error("[LDAP] Search failed: %s", exc)
            return False

        try:
            result = conn.compare(group_dn, "member", user_dn)
            logger.debug("[LDAP] compare(%s member %s) → %s", group_dn, user_dn, result)
            return result
        except Exception as exc:                               # noqa: BLE001
            logger.error("[LDAP] Compare failed: %s", exc)
            return False

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

    def __init__(self, get_response=None):
        self.get_response = get_response or self._get_response
        super().__init__(get_response)


    def process_request(self, request):
        user = request.user
        logger.debug("testing user: %s", user)

        if user.is_authenticated and not user.is_superuser:
            if not any(
                request.path.startswith(p)
                for p in (
                    settings.LOGIN_URL,
                    settings.LOGIN_WHITELIST_URL,
                    settings.ADMIN_URL,
                    settings.STATIC_URL,
                    settings.SAML_URL,
                    settings.SAML_ACS_URL,
                    "/api/v1/context",
                    "/api/v1/providers",
                )
            ):
                if self.is_authorized(user):
                    logger.info("Adding user %s to whitelist", user)
                    whitelist_group = Group.objects.get(name="whitelisted")
                    user.groups.add(whitelist_group)
                else:
                    logger.info("Filtering user %s is not authorized", user)
                    self.clear_session(request)
                    try:
                        self.send_whitelist_email(request, user)
                    except (SMTPSenderRefused, SMTPResponseException) as err:
                        logger.error("SMTP misconfigured: %s", err)
                    finally:
                        return HttpResponseRedirect(settings.LOGIN_WHITELIST_URL)
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
        logger.debug("[AUTHZ] Testing %s / %s", user.username, user.email)

        if user.email and AuthorizedUser.objects.filter(email=user.email).exists():
            logger.debug("[AUTHZ] email match in AuthorizedUser")
            return True

        if AllowWhiteListedUserOnly.is_auto_whitelisted_email(user):
            logger.debug("[AUTHZ] AUTO-pattern match → persisting email")
            # AuthorizedUser.objects.get_or_create(
            #     email=user.email, defaults={"username": user.username}
            # )
            return True

        if AuthorizedUser.objects.filter(username=user.username).exists():
            logger.debug("[AUTHZ] username match in AuthorizedUser")
            return True

        if AllowWhiteListedUserOnly._ldap_group_member(user):
            logger.debug("[AUTHZ] LDAP group match → persisting email")
            # AuthorizedUser.objects.get_or_create(
            #     email=user.email, defaults={"username": user.username}
            # )
            return True

        logger.debug("[AUTHZ] No rule matched; user is NOT authorised")
        return False


    @staticmethod
    def clear_session(request):
        request.session.flush()


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