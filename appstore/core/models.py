from django.db import models


class AuthorizedUser(models.Model):
    email = models.EmailField(max_length=254)

    def __str__(self):
        return self.email

class IrodAuthorizedUser(models.Model):
    user = models.TextField(max_length=254)
    uid = models.IntegerField()

    def __str__(self):
        return (self.user,self.uid)