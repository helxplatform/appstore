import os


from django.contrib.auth import get_user_model
from core.models import AuthorizedUser

USERS_PATH = os.environ.get("TEST_USERS_PATH", "/usr/src/inst-mgmt")

user_model = get_user_model()

with open(f"{USERS_PATH}/test-users/users.txt", "r") as users:
    for user in users.readlines():
        username, password, email = user.split(",")
        if not user_model.objects.filter(username=username).exists():
            django_user = user_model.objects.create(username=username, email=email)
            django_user.set_password(password)
            django_user.save()
            if AuthorizedUser.objects.filter(email=email):
                print(f'{"User already in Authorized Users list ----> add skipping"}')
            elif AuthorizedUser.objects.filter(username=username):
                print(f'{"User already in Authorized Users list ----> add skipping"}')
            else:
                u = AuthorizedUser(email=email, username=username)
                u.save()
                print(f"Added {username} to the Authorized Users list ----> add success")
        else:
            print(f'User "{username}" already exists, not created')
