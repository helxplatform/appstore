from django.db import models
from django.contrib.auth import get_user_model
from django_saml2_auth.user import get_user

def update_user(user):
    # as of Django_saml2_auth v3.12.0 does not add email address by default
    # to the created use entry in django db according to: 
    # https://github.com/grafana/django-saml2-auth/blob/11b97beaa2a431209e2c54103cb49c033c42ff54/django_saml2_auth/user.py#L93
    # https://github.com/grafana/django-saml2-auth/blob/11b97beaa2a431209e2c54103cb49c033c42ff54/django_saml2_auth/user.py#L165
    # This trigger gets and set the email field in the django user db
    _user = get_user(user)
    _user.email = user['email']
    _user.save()
    return _user

class AuthorizedUser(models.Model):
    email = models.EmailField(max_length=254)

    def __str__(self):
        return self.email

class IrodAuthorizedUser(models.Model):
    user = models.TextField(max_length=254)
    uid = models.IntegerField()

    def __str__(self):
        return (self.user,self.uid)