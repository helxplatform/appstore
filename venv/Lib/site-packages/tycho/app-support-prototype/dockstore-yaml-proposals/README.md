# Dockstore Service Configuration Proposals

This directory contains subdirectories of evolving example and proposed .dockstore.yml files, to try to handle
concrete services that might get registered with Dockstore.

The services are:

* Xena Hub
* JBrowse
* (not ready) [Bravo](https://github.com/statgen/bravo) -- Variant browser
* (not ready) generick8s -- this is a Kubernetes guest book example application. Using it until I can find a bioinformatics, K8s service.


### Terms

* Service -- A long running process, such as a web app or interactive application.
* .dockstore.yml -- A configuration file that describes a service.
* Launcher or Service Launcher -- An application that launches the service, using the information provided in the .dockstore.yml and the input parameter file. Examples: Leonardo, Dockstore CLI.
* User -- the consumer of the service.
* Input parameter file -- allows the user and/or launcher to specify inputs to the service, e.g., what genomics data to download, what environment variables to set.

### The .dockstore.yml

The .dockstore.yml is similar to .travis.yml and .circle-ci/config.yml; it is a file committed to a source code repository, and it describes the service. The
launcher uses the file to stand up the service. The .dockstore.yml in also used by Dockstore to surface the service in Dockstore.

The schema of the .dockstore.yml follows. For now, we will describe by example; a formal schema may follow.

```
# The dockstore.yml version; 1.1 is required for services
version: 1.1

# A required key named service
service:
  # The type is required, and can be docker-compose, kubernetes, or helm.
  type: docker-compose

  # The name of the service, required
  name: UCSC Xena Browser

  # The author, optional
  author: UCSC Genomics Institute

  # An optional description
  description: |
    The UCSC Xena browser is an exploration tool for public and private,
    multi-omic and clinical/phenotype data.
    It is recommended that you configure a reverse proxy to handle HTTPS

  # These are files the Dockstore will index. They will be directly downloadable from Dockstore. Wildcards are not supported.
  files:
     - docker-compose.yml
     - README.md
     - stand_up.sh
     - load.sh
     - port.sh
     - stop.sh
     - healthcheck.sh

  scripts:
    # The scripts section has 7 pre-defined keys. 4 are run in a defined order,
    # the other 3 are utilities that can be invoked by the service launcher.
    # Only 3 of the keys must exist and have values: start, port, and stop.
    # The other keys are optional.
    # The keys' values must be script files that are indexed (in the files section, above).

    # The service launcher will execute the scripts in the following order. All steps other than start are optional,
    # and if they are missing or have no value specified, will be ignored.
    #
    # 1. preprovision -- Invoked before any data has been downloaded and some initialization is required. Not sure if we need this one.
    # 2. prestart -- Executed after data has been downloaded locally, but before service has started (see the data section).
    # 3. start -- Starts up the service.
    # 4. postprovision -- After the service has been started. This might be invoked multiple times, e.g., if the user decides to load multiple sets of data.

    # In addition, the following scripts, if present and with a value, are for use by the launcher:
    # 1. port - Which port the service is exposing. This provides a generic way for the tool to know which port is being exposed, e.g., to reverse proxy it.
    # 2. healthcheck - exit code of 0 if service is running normally, non-0 otherwise.
    # 3. stop - stops the service

    # Since we don't have scripts for preprovision or prestart in this example, we don't specify them
    # preprovision:
    # prestart:
    start: stand_up.sh
    postprovision: load.sh

    port: port.sh
    healthcheck: healthcheck.sh
    stop: stop.sh

  environment:
    # These are environment variables that the launcher is responsible for passing to any scripts that it invokes.
    # The names must be valid environment variable names.
    # Users can specify the values of the parameters in the input parameter JSON (see below).
    # These variables are service-specific, i.e., the service creator decides what values, if any, to
    # expose as environment variables.
    # There are three parts to the environment variable
    #    - The name
    #    - An optional default value, which will be used if the user does not specify in the input file
    #    - An optional description, which can be used by the service launcher as a prompt
    #
    
    httpPort:
        default: 7222
        description: The host's HTTP port. The default is 7222.

  data:
    # This section describes data that should be provisioned locally for use by
    # the service. The service launcher is responsible for provisioning the data.
    #
    # Each key in this section is the name of a dataset. Each dataset can have
    # 1 to n files. 
    #
    # Each dataset has the following properties:
    #   - targetDirectory -- required, indicates where the files in the dataset should be downloaded to. Paths are relative.
    #   - files -- required, 1 to n files, where each file has the following attributes:
    #           - description -- a description of the file
    #           - targetDirectory -- optionally override the dataset's targetDirectory if this file needs to go in a different location.
    dataset_1:
        targetDirectory: xena/files 
        files:
            tsv:
                description: Data for Xena in TSV format

                # Could override targetDirectory here, but since all files go into xena/files, no need
                # targetDirectory:
            metadata:
                description: The metadata, in JSON format, that corresponds to the previous tsv file

```

### The Input Parameter JSON

Users specify values for their services via an input parameter JSON file. This is inspired by how parameters
are handled in CWL and WDL. The user will create an input parameter JSON file, and specify the file to the
service launcher. Alternatively, the service launcher can generate the JSON, perhaps after dynamically
prompting the user for inputs. The way the input parameter JSON is passed to the service launcher
is specific to the service launcher.

The input parameter JSON has 3 sections.

#### description

This is an optional property that describes the JSON. If the service creator wants to provide several
"pre-canned" JSON files, the descriptions can be used to distinguish between the files.

##### Example
```
{
  "description": "Loads probe map, clinical, and expression data sets.",
...
```

#### environment

This is an optional map of environment variable names to environment variable values.

##### Example

```
  ...
  "environment": {
    "httpPort": "7222"
  },
  ...
```

#### data

This section is a map of dataset names, where each dataset specifies the files to be downloaded to the local system.
Note that:
1. The name of the dataset, `dataset_1` in this case, must match a name declared in `.dockstore.yml`.
2. The names of the files within the dataset, in this case, `tsv` and `metadata`, must all match the file
names for the dataset in `.dockstore.yml`.
3. The files in the dataset are specified as an array, which allows the user to specify multiple sets of data.

```
  ...
  "data": {
    "dataset_1": [
      {
        "tsv": "https://xena.treehouse.gi.ucsc.edu/download/TreehousePEDv9_Ribodeplete_clinical_metadata.2019-03-25.tsv",
        "metadata": "https://xena.treehouse.gi.ucsc.edu/download/TreehousePEDv9_Ribodeplete_clinical_metadata.2019-03-25.tsv.json"
      },
      {
        "tsv": "https://xena.treehouse.gi.ucsc.edu/download/TreehousePEDv9_Ribodeplete_unique_ensembl_expected_count.2019-03-25.tsv",
        "metadata": "https://xena.treehouse.gi.ucsc.edu/download/TreehousePEDv9_Ribodeplete_unique_ensembl_expected_count.2019-03-25.tsv.json"
      },
      {
        "tsv": "https://xena.treehouse.gi.ucsc.edu/download/gencode.v23.annotation.gene.probemap",
        "metadata": "https://xena.treehouse.gi.ucsc.edu/download/gencode.v23.annotation.gene.probemap.json"
      }
    ]
  }
  ...
```

### TODO

* Not sure if we need the preprovision script.
* Currently the contract for the port script is to return a single port. When you run multiple services through
docker-compose, you may end up with multiple ports exposed. The idea behind this script is to return one port that
can be reverse proxied. We could change the contract to return an array of ports, but then more information
would be needed as to how the reverse proxy would route to all the different ports. For now, we will assume
just one port.
