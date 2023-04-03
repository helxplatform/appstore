#########################################################################################################
##
## Adding and Removing User to the Authorized Users table programmatically, facilitating use of secrets.
## Also handles IRODS Authorization and UID parsing
## ex: ./authorizeuser.sh heal
##
## See project docs for brand details
##
#########################################################################################################
import os
from irods.session import iRODSSession
from irods.exception import NoResultFound,UserDoesNotExist
from core.models import AuthorizedUser, IrodAuthorizedUser
import re



AUTH_USERS = os.environ.get('AUTHORIZED_USERS', '').strip()
REMOVE_AUTH_USERS = os.environ.get('REMOVE_AUTHORIZED_USERS', '').strip()
IROD_AUTH_USERS = os.environ.get('IROD_ZONE','').strip()
IROD_ZONE = os.environ.get('IROD_ZONE','').strip()
IROD_ADMIN_USN = os.environ.get('RODS_USERNAME','').strip()
IROD_ADMIN_PASS = os.environ.get('RODS_PASSWORD','').strip()
IROD_BASE_URL = os.environ.get('IROD_HOST','').strip()
IROD_PORT = int(os.environ.get('IROD_PORT','0').strip())

def irods_user_create(username,uid):
    #Check if user was already created
    if IrodAuthorizedUser.objects.filter(user=username):
        print("Irods user already found in postgres")
        return
    with iRODSSession(host=IROD_BASE_URL, port=IROD_PORT, user=IROD_ADMIN_USN, password=IROD_ADMIN_PASS, zone=IROD_ZONE) as session:
        #Check for user already existing in IRODS itself. If so, Save the user in the local database and continue
        try:
            session.users.get(username)
        except (NoResultFound,UserDoesNotExist):
            result = session.users.create(username,'rodsuser')
        else:
            print("User already exists")
        u = IrodAuthorizedUser(user=username,uid=uid)
        u.save()

if AUTH_USERS:
    users = re.split(r'[\s,]+',AUTH_USERS)
    for user in users:
        if AuthorizedUser.objects.filter(email=user):
            print(f'{"User already in Authorized Users list ----> add skipping"}')
        else:
            u = AuthorizedUser(email=user)
            u.save()
            print(f"Added {user} to the Authorized Users list ----> add success")

if IROD_AUTH_USERS:
    print("IRODS USERS ENABLED")
    with open('/etc/iroduserdata/iroduserdata','r') as f:
        for line in f:
            user,uid = line.split("::")
            irods_user_create(user,uid)
        



if REMOVE_AUTH_USERS:
    users = re.split(r'[\s,]+',REMOVE_AUTH_USERS)
    for user in users:
        a_user = AuthorizedUser.objects.filter(email=user)
        if a_user:
            a_user.delete()
            print(f"Removed {user} from Authorized Users list ----> remove success")
        else:
            print(f"{user} not in Authorized Users list ----> remove skipping")
