from django.conf import settings
from django.db import models
from django.contrib.sessions.models import Session

class AuthorizedUser(models.Model):
    email = models.EmailField(max_length=254)

    def __str__(self):
        return self.email