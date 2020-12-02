from allauth.account.forms import SignupForm
from django import forms
from django.core.mail import send_mail
from django.conf import settings


class CustomSignupForm(SignupForm):

    def __init__(self, *args, **kwargs):
        super(CustomSignupForm, self).__init__(*args, **kwargs)

    def save(self, request):
        user = super(CustomSignupForm, self).save(request)

        print('sending email')

        msg2 = 'test'
        msg = 'A new user ' + user.email + ' has signed up for access to ' + settings.APPLICATION_BRAND \
            + ' and needs to be reviewed for whitelisting. Upon successful review, kindly add the user to' \
            + ' Authorized Users on django admin panel on ' \
            + request.META['SERVER_NAME'] + ':' + request.META['SERVER_PORT'] + '/' + settings.ADMIN_URL + '.'
        send_mail(
            'Whitelisting Required',
            msg,
            settings.EMAIL_HOST_USER,
            [settings.APPLICATION_BRAND + '-admin@lists.renci.org'],
            fail_silently=False,
        )

        return user


class ResourceRequestForm(forms.Form):
    Memory_Requirement = forms.IntegerField(label="Memory Requirement")
    CPU_Requirement = forms.DecimalField(label="CPU_Requirement")
    GPU_Requirement = forms.IntegerField(label="GPU_Requirement")
