# Overview

The .dockstore.yml should provide enough information to programatically
run an instance of a Xena instance. This includes not only running Xena, but loading
it up with data.

This is an attempt for the docker-compose defined at https://github.com/coverbeck/xenahub,
i.e., once this is all worked out, the files would be checked into that repo.

## Example Usage by a client

1. Client downloads index files from Dockstore (docker-compose.yml and README.md).
2. Client downloads genomics data for Xena
    * Either using one of the pre-defined JSON files, which has references to genomics datasets on the web; Note that this isn't a very likely use case for Xena, as you would typically only install your own instance to visualize private data, but it's useful as example for services in general.
    * And/or generating a template JSON, which the user fills in, either manually or through some nice UI, and downloads.
3. Client runs the commands in the `scripts` section.

## Issues/Fuzzy Stuff

1. What if a user wants to add something the next day? The client would have to know to only run `postprovision`.
2. What if there are multiple ports?
3. Maven has resume
4. Move targetDirectory up
