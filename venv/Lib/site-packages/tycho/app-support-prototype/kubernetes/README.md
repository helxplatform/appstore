# Kubernetes

## About

This example runs a simple Node.js using Kubernetes.

## Dependencies

See this guide for [installing kubernetes locally](https://kubernetes.io/docs/tasks/tools/install-minikube/).

See this guide for how to run the [Node.js tutorial](https://kubernetes.io/docs/tutorials/hello-minikube/).  It's a simple guide.

See this guide for [minikube](https://kubernetes.io/docs/setup/minikube/).  It's a more complete guide.

At a high level:

```
brew install kubernetes-cli
brew cask install minikube
minikube start
```

## Testing

Below is how we interactively start a really minimal service using Kubernetes.  Unlike the previous example I'm not using a config file to drive the process which we really need to if we're going to have something to register on Dockstore.  Also, I need an example that uses a Dockerfile.

From https://kubernetes.io/docs/setup/minikube/

```
$ minikube start
Starting local Kubernetes cluster...
Running pre-create checks...
Creating machine...
Starting local Kubernetes cluster...

$ kubectl run hello-minikube --image=k8s.gcr.io/echoserver:1.10 --port=8080
deployment.apps/hello-minikube created
$ kubectl expose deployment hello-minikube --type=NodePort
service/hello-minikube exposed

# We have now launched an echoserver pod but we have to wait until the pod is up before curling/accessing it
# via the exposed service.
# To check whether the pod is up and running we can use the following:
$ kubectl get pod
NAME                              READY     STATUS              RESTARTS   AGE
hello-minikube-3383150820-vctvh   0/1       ContainerCreating   0          3s
# We can see that the pod is still being created from the ContainerCreating status
$ kubectl get pod
NAME                              READY     STATUS    RESTARTS   AGE
hello-minikube-3383150820-vctvh   1/1       Running   0          13s
# We can see that the pod is now Running and we will now be able to curl it:
$ curl $(minikube service hello-minikube --url)


Hostname: hello-minikube-7c77b68cff-8wdzq

Pod Information:
	-no pod information available-

Server values:
	server_version=nginx: 1.13.3 - lua: 10008

Request Information:
	client_address=172.17.0.1
	method=GET
	real path=/
	query=
	request_version=1.1
	request_scheme=http
	request_uri=http://192.168.99.100:8080/

Request Headers:
	accept=*/*
	host=192.168.99.100:30674
	user-agent=curl/7.47.0

Request Body:
	-no body in request-

# get config
$ kubectl config view
apiVersion: v1
clusters:
- cluster:
    certificate-authority: /Users/boconnor/.minikube/ca.crt
    server: https://192.168.99.100:8443
  name: minikube
contexts:
- context:
    cluster: minikube
    user: minikube
  name: minikube
current-context: minikube
kind: Config
preferences: {}
users:
- name: minikube
  user:
    client-certificate: /Users/boconnor/.minikube/client.crt
    client-key: /Users/boconnor/.minikube/client.key

$ kubectl delete services hello-minikube
service "hello-minikube" deleted
$ kubectl delete deployment hello-minikube
deployment.extensions "hello-minikube" deleted

# re-deploy from config
# see https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#creating-a-deployment
# https://github.com/kubernetes/kubernetes/issues/24873
kubectl create -f kubernetes.yaml

# shutdown
$ kubectl delete services hello-minikube
service "hello-minikube" deleted
$ kubectl delete deployment hello-minikube
deployment.extensions "hello-minikube" deleted
$ minikube stop
Stopping local Kubernetes cluster...
Stopping "minikube"...
```

## Creating

## Launching

## See Also

* This [tutorial](https://kubernetes.io/docs/tasks/configure-pod-container/configure-pod-configmap/) cover the use of config files which is what we need to have something that is independent of command line and similar to the way docker compose works.
