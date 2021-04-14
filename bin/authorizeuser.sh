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
    local brand=$1
    local AUTH_USERS=$AUTHORIZED_USERS;
    local REMOVE_AUTH_USERS=$REMOVE_AUTHORIZED_USERS;

    add () {
        if [ ! -z "$AUTH_USERS" -a "$AUTH_USERS" != " " ]; then
            USERS=(${AUTH_USERS//,/ })
            for user in "${USERS[@]}"; do
                cat <<EOF | appstore shell --settings=appstore.settings.${brand}_settings
from core.models import AuthorizedUser
if AuthorizedUser.objects.filter(email="$user"):
    print(f"User already in Authorized Users list ----> add skipping")
else:
    u = AuthorizedUser(email="$user")
    u.save()
    print(f"Added {'$user'} to the Authorized Users list ----> add success")
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
a_user = AuthorizedUser.objects.filter(email="$user")
if a_user:
    a_user.delete()
    print(f"Removed {'$user'} from Authorized Users list ----> remove success")
else:
    print(f"{'$user'} not in Authorized Users list ----> remove skipping")
EOF
            done
        fi
    }
    add;
    remove;
}

manageauthorizedusers "$1"
