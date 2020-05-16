#!/bin/bash
#pwd
if [[ ! -z $1 ]]; then
  # shellcheck disable=SC2027

  APPSTORE_HOME="${PWD}"
  export PATH=$APPSTORE_HOME/bin:$PATH
  appstore migrate_data $1
  appstore createsuperuser $1
  appstore run $1
else
  echo "please provide setting module name"
fi
