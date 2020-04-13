#!/usr/bin/env bash
set -e
echo "Starting up JBrowse"

docker-compose up -d
# Wait for server to respond before exiting
# Could instead use timeout, but not available on a Mac
attempt_counter=0
sleep_between_attempts=5
max_time_to_wait_in_seconds=300
max_attempts=$(expr ${max_time_to_wait_in_seconds} / ${sleep_between_attempts})

echo "Checking that JBrowse is up"
while ! bash healthcheck.sh ; do
    if [ ${attempt_counter} -eq ${max_attempts} ];then
      echo "Max attempts reached"
      exit 1
    fi

    printf '.'
    attempt_counter=$(($attempt_counter+1))
    sleep ${sleep_between_attempts}
done

echo "JBrowser started up"

