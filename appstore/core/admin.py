from django.contrib import admin

from core.models import AuthorizedUser


class AuthorizedUserAdmin(admin.ModelAdmin):
    fields = ['email', 'username']
    list_display = ['email', 'username']


admin.site.register(AuthorizedUser)
