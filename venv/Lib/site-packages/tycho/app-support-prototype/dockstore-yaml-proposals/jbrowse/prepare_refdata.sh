#!/usr/bin/env bash
set -e
export JDATA_DIR=`pwd`/data
echo "Loading reference data"
for filename in data/*.fa.gz; do
    echo "Loading ${filename}"
    docker run -t -v $JDATA_DIR:/jbrowse/data quay.io/coverbeck/jbrowse:feature_service /bin/bash -c "bin/prepare-refseqs.pl --fasta ${filename}"
done
