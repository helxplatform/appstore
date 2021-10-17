## Config

Two files are provided, a kubeconfig which is used by helm and kubectl to define how
to connect to the BlackBalsam cluster, and a helm values yaml file (BB-values) used to override 
the default values established by a one time initialization described below.

### Github config

It's easier to just get a github oauth application set up, navigate to
`github->Settings->Developer Setting->OAuth Apps` and create a new OAuth App.
The name is arbitrary, but should have something to do with BlackBalsam and
Kubernetes as that's what it will authorize.  There needs to be a `homepage url`
and a `authorization callback url` set as follows.

    homepage url: https://helx.<your namespace>.blackbalsam-cluster.edc.renci.org/accounts/login
    authorization callback url: https://helx.<your namespace>.blackbalsam-cluster.edc.renci.org/accounts/github/login/callback/

Create the app, and add a secret.  The client id and secret need to be copied
into BB-values.

    GITHUB_CLIENT_ID: "<the client id>"
    GITHUB_SECRET: "<the secret>"

### Helm initialization

BB-values only contains those things which are not the default, to create the default values,
the following commands need to be run 1 time per namespace (usually there will only be 1 namespace).

That the top level directory of the devops repo, set the branch to develop

#### To obtain helm configs

    git clone git@github.com:helxplatform/devops.git

and then switch to the develop branch

    git checkout develop

and execute the following helm commands

    cd helx && helm dependency update && cd -
    cd helx/charts/dug && helm dependency update && cd -
    cd helx/charts/helx-monitoring && helm dependency update && cd -
    cd helx/charts/image-utils && helm dependency update && cd -
    cd helx/charts/roger && helm dependency update && cd -
    cd helx/charts/search && helm dependency update && cd -

followed up by the specializing config

    helm -n <namespace> upgrade --install helx devops/helx --values <BB-values>
