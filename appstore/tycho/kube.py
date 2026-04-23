import json
import logging
import os
import shutil
import sys
import traceback
import base64
from time import sleep
from kubernetes import client as k8s_client, config as k8s_config
from tycho.compute import Compute
from tycho.exceptions import DeleteException
from tycho.exceptions import StartException
from tycho.exceptions import TychoException
from tycho.exceptions import ModifyException
from tycho.model import System
from tycho.tycho_utils import TemplateUtils
import kubernetes.client
from kubernetes.client.rest import ApiException

logger = logging.getLogger (__name__)

port_forwards = {}


class KubernetesCompute(Compute):
    """ A Kubernetes orchestrator implementation.

        Tested with Minikube and Google Kubernetes Engine.
    """

    def __init__(self, config):
        """ Initialize connection to Kubernetes. 
        
            Connects to Kubernetes configuration using an environment appropriate method.
        """
        super(KubernetesCompute, self).__init__()
        self.config = config
        if os.getenv('KUBERNETES_SERVICE_HOST'):
            """ We're running inside K8S. Load the config appropriately. """
            k8s_config.load_incluster_config()
        else:
            """ We're running outside of K8S. Load the config. """
            k8s_config.load_kube_config()
        api_client = k8s_client.ApiClient()
        self.api = k8s_client.CoreV1Api(api_client)
        self.rbac_api = k8s_client.RbacAuthorizationV1Api(api_client)
#        self.extensions_api = k8s_client.ExtensionsV1beta1Api(api_client) 
        self.extensions_api = k8s_client.AppsV1Api(api_client)
        self.networking_api = k8s_client.NetworkingV1Api(api_client)
        self.batch_api = k8s_client.BatchV1Api(api_client)
        self.try_minikube = True
        self.namespace = self.get_namespace (
            namespace=os.environ.get("NAMESPACE", self.get_namespace ()))
        logger.debug (f"-- using namespace: {self.namespace}")
        
    def get_namespace(self, namespace="default"):
        try:
            with open("/var/run/secrets/kubernetes.io/serviceaccount/namespace", "r") as secrets:
                for line in secrets:
                    namespace = line
                    break
        except Exception as e:
            logger.debug(f"-- downward api namespace lookup failed.")
        return namespace

    def check_volumes(self, volumes, namespace):
        try:
            volumesNA = []
            api_response = self.api.list_namespaced_persistent_volume_claim(namespace=namespace)
            for index, volume in enumerate(volumes):
                notExists = True
                if volume["volume_name"] != "stdnfs":
                    for item in api_response.items:
                        if item.metadata.name != volume["volume_name"]:
                            continue
                        else:
                            notExists = False
                            logger.info(f"PVC {volume['volume_name']} exists.")
                            break
                if notExists and volume["volume_name"] != 'stdnfs':
                    volumesNA.append(index)
                    #raise Exception(f"Cannot create system. PVC {volume['pvc_name']} does not exist. Create it.")
            return volumesNA 
        except Exception as e:
            logger.debug(f"Raising persistent volume claim exception. {e}")
            #raise

    def is_ambassador_context(self, namespace, ambassador_service_name):
        try:
            field_sel_api_response = self.api.list_namespaced_service(field_selector=f"metadata.name={ambassador_service_name}", namespace=namespace)
            return len(field_sel_api_response.items) == 1
        except ApiException as e:
            logger.info(f"There was a problem assessing whether the ambassador service is running.", e)

    def start (self, system, namespace="default"):
        """ Start an abstractly described distributed system on the cluster.
            Generate each required K8s artifact and wire them together. Currently 
            explicitly modeled elements include Deployment, PersistentVolume, 
            PersistentVolumeClaim, and Service components.

            :param system: An abstract system model.
            :type system: :class:`.System`
            :param namespace: Namespace to run the system in.
            :type namespace: str
        """
        namespace = self.namespace #system.get_namespace()
        try:
            """ Check volumes and remove them from the system. """
            volumesNA = self.check_volumes(system.volumes, namespace)
            systemVolumesCopy = []
            for index, value in enumerate(system.volumes):
                if index not in volumesNA:
                    systemVolumesCopy.append(value)
            system.volumes = systemVolumesCopy
            """ Check the status of ambassador """
            amb_status = self.is_ambassador_context(namespace, system.ambassador_service_name)
            if amb_status:
                system.amb = True
            #api_response = self.api.list_namespace()
            #notExists = True
            #for item in api_response.items:
            #    link = item.metadata.self_link
            #    app_ns = link.split("/")[-1]
            #    if app_ns == system.system_name:
            #        notExists = False
            #        logger.info(f"Namespace {system.system_name} exists. Skipping create.")
            #        break
            #if notExists:
            #    ns_manifests = system.render(template="namespace.yaml")
            #    for ns_manifest in ns_manifests:
            #        logger.info(f"Namespace {system.system_name} created.")
            #        api_response = self.api.create_namespace(body=ns_manifest)

            try:
                api_response = self.api.list_namespaced_secret(namespace=namespace)
                for item in api_response.items:
                    if item.metadata.name == f"{system.system_name}-env":
                        for key, value in item.data.items():
                            value = str(base64.b64decode(value), 'utf-8')
                            for container in system.containers:
                                container.env.append([key,TemplateUtils.render_string(value,container.env)])
                        break
            except ApiException as e:
                logger.debug(f"App requires {system.system_name}-env configmap with envs: {e}")
                ## TODO: Swallows exception.
                
            try:
                for container in system.containers:
                    if container.name == system.system_name:
                        for port in container.ports:
                            system.system_port = port['containerPort']
                            break
                    break
            except Exception as e:
                traceback.print_exc()
                exc_type, exc_value, exc_traceback = sys.exc_info()
                text = traceback.format_exception(
                    exc_type, exc_value, exc_traceback)
                raise TychoException (
                    message=f"Failed to get system port:",
                    details=text)
                ## TODO: Why not catch at the end?
                
            """ Turn an abstract system model into a cluster specific representation. """
            pod_manifests = system.render ("pod.yaml")
            #return {}
            #""" Render a persistent volume claim. """
            #pvc_manifests = system.render(template="pvc.yaml")
            #""" Create persistent volume claims. """
            #for pvc_manifest in pvc_manifests:
            #    if pvc_manifest["metadata"]["name"] != "nfs":
            #        response = self.api.create_namespaced_persistent_volume_claim(
            #            namespace=namespace,
            #            body=pvc_manifest)
            #""" Render persistent volumes. """
            #pv_manifests = system.render(template="pv.yaml")
            #""" Create the persistent volumes. """
            #for pv_manifest in pv_manifests:
            #    response = self.api.create_persistent_volume(
            #        body=pv_manifest)

            """ Create a deployment for the pod. """
            for pod_manifest in pod_manifests:
                deployment,create_deployment_api_response = self.pod_to_deployment (
                    name=system.name,
                    username=system.username,
                    identifier=system.identifier,
                    template=pod_manifest,
                    namespace=namespace)

            """ Create a network policy if appropriate. """
            if system.requires_network_policy ():
                logger.debug ("creating network policy")
                network_policy_manifests = system.render (
                    template="policy/tycho-default-netpolicy.yaml")
                for network_policy_manifest in network_policy_manifests:
                    logger.debug (f"applying network policy: {network_policy_manifest}")
                    network_policy = self.networking_api.create_namespaced_network_policy (
                        body=network_policy_manifest,
                        namespace=namespace)

            """ Create service endpoints. """
            container_map = {}
            counter = 0
            for container in system.containers:
                """ Determine if a service is configured for this container. """
                service = system.services.get (container.name, None)
                if service:
                    logger.debug (f"generating service for container {container.name}")
                    service_manifests = system.render (
                        template = "service.yaml",
                        context = { "service" : service, "create_deployment_api_response":create_deployment_api_response }
                    )
                    for service_manifest in service_manifests:
                        logger.debug (f"-- creating service for container {container.name}")                        
                        response = self.api.create_namespaced_service(
                            body=service_manifest,
                            namespace=namespace)

                        ip_address = None
                        if not system.amb:
                            ip_address = self.get_service_ip_address (response)

                        """ Return generated node ports to caller. """
                        for port in response.spec.ports:
                            container_map[container.name] = {
                                "ip_address" : ip_address,
                                port.name    : port.node_port
                            }
                            break
            result = {
                'name'       : system.name,
                'sid'        : system.identifier,
                'containers' : container_map,
                'conn_string': system.conn_string
            }
        
        except Exception as e:
            self.delete (system.name)
            exc_type, exc_value, exc_traceback = sys.exc_info()
            text = traceback.format_exception(
                exc_type, exc_value, exc_traceback)
            raise StartException (
                message=f"Unable to start system: {system.name}",
                details=text)

        logger.info (f"result of the app launch: {json.dumps(result,indent=2)}")
        return result

    def get_service_ip_address (self, service_metadata):
        """ Get the IP address for a service. On a system with a load balancer
            that will be in the service status' load balancer section. On minikube,
            we use the minikube IP address which is in the system config. 


            :param service: Service metadata.
            :returns: ip_address IP Address of the service.
            """
        ip_address = None if os.environ.get("DEV_PHASE", "prod") != "test" else "127.0.0.1"
        try:
            app_id = service_metadata.metadata.labels["tycho-app"]
            logger.info (f"-================================> *** {app_id}")
            if not app_id in port_forwards:
                port_forwards[app_id] = app_id #process.pid
                sleep (3)
                logger.debug (f"--------------> {service_metadata.spec.ports}")
                port = service_metadata.spec.ports[0].port
                node_port = service_metadata.spec.ports[0].node_port
                if node_port is None:
                    node_port = service_metadata.spec.ports[0].target_port
                exe = shutil.which ('kubectl')
                command = f"{exe} port-forward --pod-running-timeout=3m0s deployment/{app_id} {node_port}:{port}"
                logger.debug (f"-- port-forward: {command}")
            #ip_address = "127.0.0.1"
        except Exception as e:
            traceback.print_exc ()
        logger.debug (f"service {service_metadata.metadata.name} ingress ip: {ip_address}")
        return ip_address

    def pod_to_deployment (self, name, username, identifier, template, namespace="default"):
        """ Create a deployment specification based on a pod template.
            
            :param name: Name of the system.
            :type name: str
            :param template: Relative path to the template to use.
            :type template: str
            :param identifier: Unique key to this system.
            :type identifier: str
            :param namepsace: Namespace to run the pod in.
            :type namespace: str
        """
        namespace = self.namespace #self.get_namespace()
        deployment_spec = k8s_client.V1DeploymentSpec(
            replicas=1,
            template=template,
            selector=k8s_client.V1LabelSelector (
                match_labels = {
                    "tycho-guid" : identifier,
                    "username"   : username
                }))
        
        """ Instantiate the deployment object """
        logger.debug (f"creating deployment specification {template}")
        deployment = k8s_client.V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=k8s_client.V1ObjectMeta(
                name=name,
                labels={
                    "tycho-guid" : identifier,
                    "executor" : "tycho",
                    "username" : username
                }),
            spec=deployment_spec)

        """ Create the deployment. """
        logger.debug (f"applying deployment {template}")
        api_response = self.extensions_api.create_namespaced_deployment(
            body=deployment,
            namespace=namespace)
        logger.debug (f"deployment created. status={api_response.status}")
        return deployment,api_response

    def delete (self, name, namespace="default"):
        """ Delete the deployment. 
                
            :param name: GUID of the system to delete.
            :type name: str
            :param namespace: Namespace the system runs in.
            :type namespace: str
        """
        namespace = self.namespace #self.get_namespace()
        try: 
            """ Treat everything with a namespace parameterized collections based delete 
            operator the same. """
            finalizers = {
                "deployment"  : self.extensions_api.delete_collection_namespaced_deployment,
                "replica_set" : self.extensions_api.delete_collection_namespaced_replica_set,
                "pod"         : self.api.delete_collection_namespaced_pod,
                # "persistentvolumeclaim" : self.api.delete_collection_namespaced_persistent_volume_claim,
                #"networkpolicy" : self.networking_api.delete_collection_namespaced_network_policy
            }
            for object_type, finalizer in finalizers.items ():
                logger.debug (f" --deleting {object_type} elements of {name} in namespace {namespace}")
                response = finalizer (
                    label_selector=f"tycho-guid={name}",
                    namespace=namespace)
            
        except ApiException as e:
            traceback.print_exc()
            exc_type, exc_value, exc_traceback = sys.exc_info()
            text = traceback.format_exception(
                exc_type, exc_value, exc_traceback)
            raise DeleteException (
                message=f"Failed to delete system: {name}",
                details=text)
        return {
        }
    
    def status (self, name=None, username=None, namespace="default"):
        """ Get status.
            Without a name, this will get status for all running systems.
            With a name, it will get status for the specified system.

            :param name: GUID of a system to get status for.
            :type name: str
            :param namespace: Namespace the system runs in.
            :type namespace: str
        """
        namespace = self.namespace
        result = []

        """ Find all our generated deployments. """
        label = f"tycho-guid={name}" if name else f"executor=tycho"
        if username:
            label = f"username={username}" if username else f"executor=tycho"
        logger.debug (f"-- status label: {label}")
        response = self.extensions_api.list_namespaced_deployment (
            namespace,
            label_selector=label)

        if response is not None:
            for item in response.items:

                """ Collect pod metrics for this deployment. """
                pod_resources = {
                    container.name : container.resources.limits
                    for container in item.spec.template.spec.containers
                }
                logger.debug(f"-- pod-resources {pod_resources}")

                item_guid = item.metadata.labels.get("tycho-guid", None)
                item_username = item.metadata.labels.get("username", None)

                """ Get the creation timestamp"""
                c_time = item.metadata.creation_timestamp
                time = f"{c_time.month}-{c_time.day}-{c_time.year} {c_time.hour}:{c_time.minute}:{c_time.second}"

                """ Get the workspace name of the pod """
                workspace_name = item.spec.template.metadata.labels.get("app-name", "")

                """ Temporary variables so rest of the code doesn't break elsewhere. """
                ip_address = "127.0.0.1"
                port = 80

                desired_replicas = item.status.replicas
                ready_replicas = item.status.ready_replicas
                is_ready = ready_replicas == desired_replicas

                result.append(
                    {
                        "name": item.metadata.name,
                        "app_id": item.spec.template.metadata.labels.get('original-app-name', None),
                        "sid": item_guid,
                        "ip_address": ip_address,
                        "port": str(port),
                        "creation_time": time,
                        "username": item_username,
                        "utilization": pod_resources,
                        "workspace_name": workspace_name,
                        "is_ready": is_ready
                    }
                )

        return result

    def modify(self, system_modify):
        """
           Returns a list of all patches,

               * metadata labels - Applied to each deployment resource including the pods managed by it.
               * container resources - Are applied to each container in the pod managed by a deployment.

           Takes in a handle :class:`tycho.model.ModifySystem` with the following instance variables,

               * config - A default config for Tycho.
               * guid - A unique guid to a system/deployment.
               * labels - A dictionary of labels.
               * resources - A dictionary containing cpu and memory as keys.
               * containers - A list of containers the resources are applied to.

           :param system_modify: Spec and Metadata object
           :type system_modify: class ModifySystem

           :returns: A list of patches applied
           :rtype: A list

        """
        namespace = self.namespace
        patches_applied = list()
        try:
            api_response = self.extensions_api.list_namespaced_deployment(
                label_selector=f"tycho-guid={system_modify.guid}",
                namespace=namespace).items

            if len(api_response) == 0:
                raise Exception("No deployments found. Specify a valid GUID. Format {'guid': '<name>'}.")

            for deployment in api_response:

                system_modify.containers = list()
                # Need this step to get a comprehensive list of containers if it's multi container pod.
                # Later for patching would need a merge key "name" and corresponding image.
                containers = deployment.spec.template.spec.containers
                system_modify.containers = containers

                generator = TemplateUtils(config=system_modify.config)
                templates = list(generator.render("patch.yaml", context={"system_modify": system_modify}))
                patch_template = templates[0] if len(templates) > 0 else {}
                patches_applied.append(patch_template)

                _ = self.extensions_api.patch_namespaced_deployment(
                        name=deployment.metadata.name,
                        namespace=namespace,
                        body=patch_template
                    )

            return {
                "patches": patches_applied
            }

        except (IndexError, ApiException, Exception) as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            text = traceback.format_exception(exc_type, exc_value, exc_traceback)
            raise ModifyException(
                message=f"Failed to modify system: {system_modify.guid}",
                details=text
            )

    # ------------------------------------------------------------------
    # Batch Job support
    # ------------------------------------------------------------------

    def start_job(self, name, identifier, image, command, env, volumes,
                  limits, namespace=None, username="mism",
                  service_account=None):
        """Create a K8s Job for batch execution. No Service, no Ambassador.

        Args:
            name: Job name prefix
            identifier: UUID for labeling (correlation key)
            image: Container image
            command: Entrypoint command list (or None for image default)
            env: Dict of environment variables
            volumes: List of dicts with keys: name, pvc, mount_path, sub_path, read_only
            limits: Dict with keys: cpus, memory
            namespace: K8s namespace (defaults to self.namespace)
            username: User who triggered the job (for labels)
            service_account: K8s ServiceAccount (optional)

        Returns:
            dict with keys: name, sid, status
        """
        namespace = namespace or self.namespace
        full_name = f"{name}-{identifier}"

        # Build container env
        env_list = [k8s_client.V1EnvVar(name=k, value=str(v)) for k, v in env.items()]
        env_list.append(k8s_client.V1EnvVar(name="MISM_GUID", value=identifier))

        # Build volume mounts and volumes — deduplicate PVCs by claim name
        volume_mounts = []
        k8s_volumes = []
        seen_pvcs = set()
        for vol in volumes:
            vol_name = vol["pvc"]  # use PVC name as volume name (dedup)
            volume_mounts.append(k8s_client.V1VolumeMount(
                name=vol_name,
                mount_path=vol["mount_path"],
                sub_path=vol.get("sub_path"),
                read_only=vol.get("read_only", False),
            ))
            if vol_name not in seen_pvcs:
                k8s_volumes.append(k8s_client.V1Volume(
                    name=vol_name,
                    persistent_volume_claim=k8s_client.V1PersistentVolumeClaimVolumeSource(
                        claim_name=vol["pvc"],
                    ),
                ))
                seen_pvcs.add(vol_name)

        # Build resource requirements
        resources = k8s_client.V1ResourceRequirements(
            limits={"cpu": limits.get("cpus", "1"), "memory": limits.get("memory", "2Gi")},
            requests={"cpu": limits.get("cpus", "1"), "memory": limits.get("memory", "2Gi")},
        )

        # Build container
        container = k8s_client.V1Container(
            name=name[:63],
            image=image,
            command=command if command else None,
            env=env_list,
            resources=resources,
            volume_mounts=volume_mounts if volume_mounts else None,
        )

        # Build pod spec
        pod_spec = k8s_client.V1PodSpec(
            restart_policy="Never",
            containers=[container],
            volumes=k8s_volumes if k8s_volumes else None,
            service_account_name=service_account,
            enable_service_links=False,
        )

        labels = {
            "mism-guid": identifier,
            "executor": "mism-exec",
            "username": username,
            "app-name": name,
        }

        # Build Job
        job = k8s_client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=k8s_client.V1ObjectMeta(name=full_name, labels=labels),
            spec=k8s_client.V1JobSpec(
                template=k8s_client.V1PodTemplateSpec(
                    metadata=k8s_client.V1ObjectMeta(labels=labels),
                    spec=pod_spec,
                ),
                backoff_limit=0,
            ),
        )

        try:
            self.batch_api.create_namespaced_job(body=job, namespace=namespace)
            logger.info(f"Job created: {full_name}")
            return {
                "name": full_name,
                "sid": identifier,
                "status": "running",
            }
        except ApiException as e:
            raise StartException(
                message=f"Failed to create job {full_name}",
                details=str(e),
            )

    def job_status(self, sid, namespace=None):
        """Get the status of a batch Job by its identifier."""
        namespace = namespace or self.namespace
        try:
            response = self.batch_api.list_namespaced_job(
                namespace=namespace,
                label_selector=f"mism-guid={sid}",
            )
        except ApiException:
            logger.exception(f"Failed to get job status for sid={sid}")
            return None

        if not response.items:
            return None

        job = response.items[0]
        job_status = job.status

        status = "pending"
        phase = "pending"
        exit_code = None

        if job_status.succeeded and job_status.succeeded > 0:
            status = "succeeded"
            phase = "succeeded"
        elif job_status.failed and job_status.failed > 0:
            status = "failed"
            phase = "failed"
        elif job_status.active and job_status.active > 0:
            status = "running"
            phase = "running"
        else:
            # Fall back to pod-level inspection
            pod_info = self._get_job_pod_phase(sid, namespace)
            phase = pod_info.get("phase", "unknown")
            exit_code = pod_info.get("exit_code")
            if phase == "succeeded":
                status = "succeeded"
            elif phase == "failed":
                status = "failed"

        return {
            "sid": sid,
            "name": job.metadata.name,
            "status": status,
            "phase": phase,
            "exit_code": exit_code,
        }

    def delete_job(self, sid, namespace=None):
        """Delete a batch Job and its pods by identifier."""
        namespace = namespace or self.namespace
        label = f"mism-guid={sid}"
        try:
            self.batch_api.delete_collection_namespaced_job(
                namespace=namespace,
                label_selector=label,
                propagation_policy="Background",
            )
            self.api.delete_collection_namespaced_pod(
                namespace=namespace, label_selector=label,
            )
            logger.info(f"Deleted job sid={sid}")
        except ApiException:
            logger.exception(f"Failed to delete job sid={sid}")
            raise DeleteException(
                message=f"Failed to delete job sid={sid}",
            )

    def _get_job_pod_phase(self, sid, namespace):
        """Inspect the pod backing a Job for exit code."""
        try:
            pods = self.api.list_namespaced_pod(
                namespace=namespace,
                label_selector=f"mism-guid={sid}",
            )
            if not pods.items:
                return {"phase": "unknown"}

            pod = pods.items[0]
            raw_phase = (pod.status.phase or "Unknown").lower()

            if pod.status.container_statuses:
                for cs in pod.status.container_statuses:
                    if cs.state and cs.state.terminated:
                        code = cs.state.terminated.exit_code
                        return {
                            "phase": "succeeded" if code == 0 else "failed",
                            "exit_code": code,
                        }

            return {"phase": raw_phase}
        except ApiException:
            return {"phase": "unknown"}



'''
our-pvc:
  - dicom images                    ro-sidecar
  - nfsrods for napari and imagej   irods
  - deepgtex                        rwm

Given:
==============================================================
docker-compose.yaml:
   ...
   volumes:
     pvc://deepgtex:/deepgtex:rw                    RW!
     pvc://nfsrods:/nfsrods:rw                      RW?     
--------------------------------------------------------------    
every container
*   pvc://stdnfs/home/${username} -> /home/${username}   RW
*   pvc://stdnfs/data             -> /shared             R
    sidecar?                      -> /data               R

options
   user provides a pvc  -> use that as pvc://stdnfs

------

cluster A:
  my-pvc is a RWM pvc.
  bin/tycho api --docker --pvc my-pvc

cluster B:
  pvc-2 is a RWM pvc
  bin/tycho api --docker --pvc pvc-2

------

clusterA:
  my-rwm-storage-class
  bin/tycho api --docker --rwm-sc my-rwm-storage-class
'''
