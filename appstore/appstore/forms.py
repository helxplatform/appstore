from allauth.account.forms import SignupForm
from django import forms
from django.core.mail import send_mail
from django.conf import settings


class CustomSignupForm(SignupForm):
    def __init__(self, *args, **kwargs):
        super(CustomSignupForm, self).__init__(*args, **kwargs)

    def save(self, request):
        user = super(CustomSignupForm, self).save(request)
        return user


class ResourceRequestForm(forms.Form):
    Memory_Requirement = forms.IntegerField(label="Memory Requirement")
    CPU_Requirement = forms.DecimalField(label="CPU_Requirement")
    GPU_Requirement = forms.IntegerField(label="GPU_Requirement")
