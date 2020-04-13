#!/usr/bin/env bash
set -e
curl -s -o /dev/null --fail localhost:${HTTP_PORT:-3000}/data/tracks.conf
