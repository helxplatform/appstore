#!/bin/bash
set -ex

#########################################################################################################
##
## Adding and Removing User to the Authorized Users table programmatically, facilitating use of secrets.
##
## ex: ./authorizeuser.sh heal
##
## See project docs for brand details
##
#########################################################################################################
manageauthorizedusers () {
    local BRAND_MODULE=$1
    local AUTH_USERS=$AUTHORIZED_USERS;
    local REMOVE_AUTH_USERS=$REMOVE_AUTHORIZED_USERS;

    add () {
        if [ ! -z "$AUTH_USERS" -a "$AUTH_USERS" != " " ]; then
            USERS=(${AUTH_USERS//,/ })
            for user in "${USERS[@]}"; do
                cat <<EOF | appstore shell --settings=${BRAND_MODULE}
from core.models import AuthorizedUser
is_email = re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$',user) is not None
is_authorized_user = AuthorizedUser.objects.filter(email="$user") if is_email else AuthorizedUser.objects.filter(username="$user")
if is_authorized_user:
    print(f"User {"$user"} already in Authorized Users list ----> add skipping")
else:
    u = AuthorizedUser(email="$user") if is_email else AuthorizedUser(username="$user")
    u.save()
    print(f"Added {"$user"} to the Authorized Users list ----> add success")    
EOF
            done
        fi
    }

    remove () {
        if [ ! -z "$REMOVE_AUTH_USERS" -a "$REMOVE_AUTH_USERS" != " " ]; then
            USERS=(${REMOVE_AUTH_USERS//,/ })
            for user in "${USERS[@]}"; do
                cat <<EOF | appstore shell --settings=appstore.settings.${brand}_settings
from core.models import AuthorizedUser
is_email = re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$',user) is not None
a_user = AuthorizedUser.objects.filter(email=$user) if is_email else AuthorizedUser.objects.filter(username=$user)
if a_user:
    a_user.delete()
    print(f"Removed {user} from Authorized Users list ----> remove success")
else:
    print(f"{$user} not in Authorized Users list ----> remove skipping")
EOF
            done
        fi
    }
    add;
    remove;
}

manageauthorizedusers "$1"
