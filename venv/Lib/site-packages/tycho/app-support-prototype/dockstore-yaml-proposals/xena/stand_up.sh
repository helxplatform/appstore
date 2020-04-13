#!/usr/bin/env bash
set -e
echo "Starting up Xena Hub"

# docker-compose has variables in caps
export HTTP_PORT=$httpPort
export HTTPS_PORT=$httpsPort

docker-compose up -d
# Wait for server to respond before exiting
# Could instead use timeout, but not available on a Mac
attempt_counter=0
sleep_between_attempts=5
max_time_to_wait_in_seconds=300
max_attempts=$(expr ${max_time_to_wait_in_seconds} / ${sleep_between_attempts})

echo "Checking that Xena Hub is up"
while [[ "$(curl -s -o /dev/null -w ''%{http_code}'' localhost:${httpPort}/ping/)" != "200" ]]; do
    if [ ${attempt_counter} -eq ${max_attempts} ];then
      echo "Max attempts reached"
      exit 1
    fi

    printf '.'
    attempt_counter=$(($attempt_counter+1))
    sleep ${sleep_between_attempts}
done

echo "Xena Hub started up"
