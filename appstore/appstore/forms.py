from allauth.account.forms import SignupForm
from django import forms
from django.core.mail import send_mail
from django.conf import settings


class CustomSignupForm(SignupForm):

    def __init__(self, *args, **kwargs):
        super(CustomSignupForm, self).__init__(*args, **kwargs)

    def save(self, request):
        user = super(CustomSignupForm, self).save(request)

        send_mail(
            'Whitelisting Required',
            'A new user ' + user.email + ' has signed up for access to ' + settings.APPLICATION_BRAND
            + 'and needs to be reviewed for whitelisting. Upon successful review, kindly whitelist the user using '
            + settings.SITE_URL + settings.ADMIN_URL,
            settings.EMAIL_HOST_USER,
            [settings.APPLICATION_BRAND + '-admin@lists.renci.org'],
            fail_silently=False,
        )

        return user


class ResourceRequestForm(forms.Form):
    Memory_Requirement = forms.IntegerField(label="Memory Requirement")
    CPU_Requirement = forms.DecimalField(label="CPU_Requirement")
    GPU_Requirement = forms.IntegerField(label="GPU_Requirement")
