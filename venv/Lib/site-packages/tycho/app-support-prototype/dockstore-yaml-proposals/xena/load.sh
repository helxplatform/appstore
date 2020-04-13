#!/usr/bin/env bash
set -e
echo "Loading data into Xena Hub"
for filename in xena/files/*.{tsv,probemap}; do
    tsv=$(basename $filename)
    echo Loading ${tsv}
    docker exec xena java -jar /ucsc_xena/cavm-0.24.0-standalone.jar --load /root/xena/files/${tsv}
done
