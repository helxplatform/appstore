from django.conf import settings

def global_settings(request):
   return { 'APPLICATION_BRAND': settings.APPLICATION_BRAND,
            'ALLOW_DJANGO_LOGIN': settings.ALLOW_DJANGO_LOGIN}
