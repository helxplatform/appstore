# AppStore Auth Flow

The HeLx Appstore supports the following login types:

| Type     | ENVIRONMENT_VARIABLE |
| -------- | -------------------- |
| Django   | ALLOW_DJANGO_LOGIN   |
| OAuth    | OAUTH_PROVIDERS      |
| SAML SSO | ALLOW_SAML_LOGIN     |

OAuth and SAML login require additional configuration as detailed below.

## OAuth Social Login

HeLx Appstore is currently deployed and tested with social authentication
using the [django-allauth](https://django-allauth.readthedocs.io/en/latest/installation.html) package.
To configure oauth you need to setup your provider oauth application detailed
[here](https://django-allauth.readthedocs.io/en/latest/installation.html).

> Tip you can use a local address (for instance `0.0.0.0:8000`) when
> configuring the oauth homepage and callback urls for local dev/test
> or setup a hostname in /etc/hosts.

### Social Application Setup

To pre configure the social providers in django set the following environment variables:

- OAUTH_PROVIDERS
- \<PROVIDER>_CLIENT_ID
- \<PROVIDER>_SECRET
- \<PROVIDER>_NAME

And run:

```bash
DEV_PHASE=stub python manage.py addingwhitelistedsocialapp --settings=$settings  &&\
```

This executes the command found in `core/management/commands/addingwhitelistedsocialapp.py`
Populating the `social_app` and `social_app_sites` tables. Inspect these in the local `DATABASE.sqlite3` for more information.

Sites can also be configured via the admin panel -> "Social Accounts"

![Admin Panel Social Auth](./assets/images/admin-panel-social-auth.png)

> More information is available in the [devops](https://github.com/helxplatform/devops#configure-environment-variables-for-helx-deployment)
configuration and [appstore](https://github.com/helxplatform/appstore/blob/develop/appstore/README.md#app-development)
docs.

### Authentication Flow

When logging in with a social provider the following steps occur:

1. Navigate to the appstore
![Appstore Login Page](./assets/images/appstore-login.png)
1. Direct to the provider login url (ex: GitHub, Google)
1. Login with provider, if this is the first time grant the oauth app permissions
1. Provider redirects to the authorization callback url
1. Django verifies that the app is registered for this site (`SITE_ID`), see `socialaccount_socialapp` and `socialaccount_socialapp_sites`
![Social Auth Table](./assets/images/social-auth-socialaccount-socialapp.png)
![Social Auth Table](./assets/images/social-auth-socialaccount-socialsite.png)
1. The user is setup in `auth_user` if they do not exist
1. The `AllowWhiteListedUserOnly` middleware checks if the user should be allowed to
view a page after being authenticated
1. Assuming an authenticated and whitelisted `User` Django sets up a session, and allauth
stores a token for the user in `socialaccount_socialtoken`
![Social Auth Table](./assets/images/social-auth-socialaccount-socialtoken.png)
1. Inside of `core/views.py` there is a [Django signal receiver](https://docs.djangoproject.com/en/3.1/topics/signals/#connecting-receiver-functions)
that connects to an [allauth signal](https://django-allauth.readthedocs.io/en/latest/signals.html?highlight=pre_social_login#allauth-socialaccount)
and adds the user token as `Authorization` to the session
1. The user is now authenticated and able to navigate to the apps page or other endpoints

> The middleware checks the relationship between the whitelist group in `auth_group` and the user `auth_user` via `auth_users_groups`. See `AUTHORIZED_USERS` for setting this up locally or in deployment. This can also be managed via the admin panel.

> This demo application has since been deleted


## SAML SSO Login

> TODO - detail UNC Onyen SSO/SAML auth flow
