#########################################################################################################
##
## Adding and Removing User to the Authorized Users table programmatically, facilitating use of secrets.
##
## ex: ./authorizeuser.sh heal
##
## See project docs for brand details
##
#########################################################################################################
import os

from core.models import AuthorizedUser

AUTH_USERS = os.environ.get('AUTHORIZED_USERS', '').strip()
REMOVE_AUTH_USERS = os.environ.get('REMOVE_AUTHORIZED_USERS', '').strip()

if AUTH_USERS:
    users = AUTH_USERS.split(',')
    for user in users:
        if AuthorizedUser.objects.filter(email=user):
            print(f"User already in Authorized Users list ----> add skipping")
        else:
            u = AuthorizedUser(email=user)
            u.save()
            print(f"Added {user} to the Authorized Users list ----> add success")

if REMOVE_AUTH_USERS:
    users = REMOVE_AUTH_USERS.split(',')
    for user in users:
        a_user = AuthorizedUser.objects.filter(email=user)
        if a_user:
            a_user.delete()
            print(f"Removed {user} from Authorized Users list ----> remove success")
        else:
            print(f"{user} not in Authorized Users list ----> remove skipping")
