#!/bin/bash
set -ex

###############################################################################
##
##  This script presents a shell utility for creating a Django super user.
##   
## ex: ./superuser.sh heal
##
## See project docs for brand details
##
###############################################################################
createsuperuser () {
    # In production, set environment variables.
    # In kubernetes, set the environment variables via secrets.
    create_superuser() {

    local brand=$1
    local SUPERUSERNAME=${APPSTORE_DJANGO_USERNAME:-admin}
    local SUPERUSEREMAIL=""
    local SUPERUSERPASSWORD=${APPSTORE_DJANGO_PASSWORD:-admin}
    cat <<EOF | appstore shell --settings=appstore.settings.${brand}_settings
from django.contrib.auth import get_user_model

User = get_user_model()

if not User.objects.filter(username="$SUPERUSERNAME").exists():
    User.objects.create_superuser("$SUPERUSERNAME", "$SUPERUSEREMAIL", "$SUPERUSERPASSWORD")
else:
    print('User "{}" already exists, not created'.format("$SUPERUSERNAME"))
EOF
  }
  create_superuser "$1"
}

createsuperuser "$1"