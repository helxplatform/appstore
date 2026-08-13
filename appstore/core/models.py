import secrets
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session as SessionModel
from django.core.exceptions import ValidationError
from datetime import timedelta
from string import ascii_letters, digits, punctuation

UserModel = get_user_model()

def generate_token():
        token = "".join(secrets.choice(ascii_letters + digits) for i in range(256))
        # Should realistically never occur, but it's possible.
        while UserIdentityToken.objects.filter(token=token).exists():
            token = "".join(secrets.choice(ascii_letters + digits) for i in range(256))
        return token

def user_token_expires():
    return timezone.now() + timedelta(days=31)

class AuthorizedUser(models.Model):
    email = models.EmailField(max_length=254, blank=True)
    username = models.CharField(max_length=128, blank=True)

    def __str__(self):
        return f"{self.email}, {self.username}"

    def clean(self):
        if not self.email and not self.username:
            raise ValidationError("Please enter a value for either email and/or username. Both cannot be empty.")

class IrodAuthorizedUser(models.Model):
    user = models.TextField(max_length=254)
    uid = models.IntegerField()

    def __str__(self):
        return f"{self.user}, {self.uid}"
    
class UserIdentityToken(models.Model):
    user = models.ForeignKey(UserModel, on_delete=models.CASCADE)

    token = models.CharField(max_length=256, unique=True, default=generate_token)
    # Optionally, identify the consumer (probably an app) whom the token was generated for.
    consumer_id = models.CharField(max_length=256, default=None, null=True)
    expires = models.DateTimeField(default=user_token_expires)

    @property
    def valid(self):
        return timezone.now() <= self.expires
    
    @staticmethod
    def compute_app_consumer_id(system_id):
        return f"{ system_id }"

    def __str__(self):
        return f"{ self.user.get_username() }-token-{ self.pk }"
        