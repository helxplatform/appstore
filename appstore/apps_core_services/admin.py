from django.contrib import admin

from apps_core_services.models import AuthorizedUser


class AuthorizedUserAdmin(admin.ModelAdmin):
    fields = ['email']
    list_display = 'email'


admin.site.register(AuthorizedUser)
