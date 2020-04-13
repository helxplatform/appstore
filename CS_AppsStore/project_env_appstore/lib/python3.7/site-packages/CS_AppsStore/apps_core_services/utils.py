import requests
import uuid
import datetime
import json

from django.utils import timezone
from django.http import HttpResponseRedirect, JsonResponse
from django.conf import settings
from django.contrib.auth import authenticate, login as auth_login


def authenticate_user(request, username=None, access_token=None, name=None, email=None):
    if name:
        namestrs = name.split(' ')
        fname = namestrs[0]
        lname = namestrs[-1]
    else:
        fname = ''
        lname = ''

    tgt_user = None
    if username and access_token:
        kwargs = {}
        kwargs['request'] = request
        kwargs['username'] = username
        kwargs['access_token'] = access_token
        kwargs['first_name'] = fname
        kwargs['last_name'] = lname
        kwargs['email'] = email
        tgt_user = authenticate(**kwargs)
        if tgt_user:
            auth_login(request, tgt_user)

    return tgt_user


def get_auth_redirect(request):
    # set return_to to be where user is redirected back to upon successful login
    # it needs to be somewhere that will handle the access_token url parameter, which
    # can be the url of the current app, since check_authorization will check for it
    # right now this is restricted to domains matching '*.commonsshare.org'
    return_url = '&return_to={}://{}/apps'.format(request.scheme, request.get_host())
    url = '{}authorize?provider=auth0'.format(settings.OAUTH_SERVICE_SERVER_URL)
    url += '&scope=openid%20profile%20email'
    url += return_url
    auth_header_str = 'Basic {}'.format(settings.OAUTH_APP_KEY)
    resp = requests.get(url, headers={'Authorization': auth_header_str},
                        verify=False)
    body = json.loads(resp.content.decode('utf-8'))
    return HttpResponseRedirect(body['authorization_url'])


def check_authorization(request):
    token = request.GET.get("token")
    now = timezone.now
    if not token:
        token = request.GET.get("access_token")
    r_invalid = get_auth_redirect(request)
    skip_validate = False
    if 'HTTP_AUTHORIZATION' in request.META:
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        if not auth_header:
            return r_invalid
        terms = auth_header.split()
        if len(terms) != 2:
            return r_invalid
        elif terms[0] == 'Bearer':
            token = terms[1]
        else:
            return r_invalid
    elif 'token' in request.GET:
        token = request.GET.get('token')
    elif 'access_token' in request.GET:
        token = request.GET.get('access_token')
    elif 'session_id' in request.session and request.session.get_expiry_date() >= now():
        skip_validate = True
    else:
        return r_invalid

    if not skip_validate:
        # need to check the token validity
        auth_url = settings.OAUTH_SERVICE_SERVER_URL
        validate_url = auth_url + 'validate_token?access_token='
        resp = requests.get(validate_url + token)
        if resp.status_code == 200:
            body = json.loads(resp.content.decode('utf-8'))
            if body.get('active', False):
                # the token was valid, set a session
                request.session['session_id'] = str(uuid.uuid4())
                request.session.set_expiry(datetime.timedelta(days=30).total_seconds())
                uname = body.get('username', None)
                uemail = body.get('email', None)
                name = body.get('name', None)
                ret_user = authenticate_user(request, username=uname, access_token=token,
                                             name=name, email=uemail)
                if ret_user:
                    return JsonResponse(status=200, data={
                        'status_code': 200,
                        'message': 'Successful authentication',
                        'user': uname})

            r = JsonResponse(status=403, data={
                'status_code': 403,
                'message': 'Request forbidden'})
            return r
        else:
            # picked up existing valid session, no need to check again
            return JsonResponse(status=403, data={'status_code': 403, 'message': 'forbidden'})
    else:
        # picked up existing valid session, no need to check again
        return JsonResponse(status=200, data={'status_code': 200, 'message': 'session was valid'})
