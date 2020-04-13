import argparse
import logging
import ipaddress
import json
import os
import uuid
import yaml
from tycho.tycho_utils import TemplateUtils

logger = logging.getLogger (__name__)

class Limits:
    """ Abstraction of resource limits on a container in a system. """
    def __init__(self,
                 cpus=None,
                 gpus=None,
                 memory=None):
        """ Create limits.
            
            :param cpus: Number of CPUs. May be a fraction.
            :type cpus: str
            :param gpus: Number of GPUs. May be a fraction.
            :type gpus: str
            :param memory: Amount of memory 
            :type memory: str
        """
        self.cpus = cpus
        self.gpus = gpus
        #assert (self.gpus).is_integer, "Fractional GPUs not supported"
        self.memory = memory
    def __repr__(self):
        return f"cpus:{self.cpus} gpus:{self.gpus} mem:{self.memory}"

class Volumes:
    def __init__(self, name, name_noiden, containers):
        self.name = name
        self.name_noiden = name_noiden
        self.containers = containers
        self.volumes = []

    def process_volumes(self):
        try:
            for index, volume in enumerate(self.containers[0]['volumes']):
                volume_name = f"{self.name}-{index}"
                claim_name = f"pvc-for-{volume_name}"
                try:
                  if 'gpus' in self.containers[0]['limits'].keys():
                    disk_name = f"{self.name_noiden}-{index}-gpu-disk"
                  else:
                    disk_name = f"{self.name_noiden}-{index}-default-disk"
                except Exception as e:
                  print(f"resource limits have to be specified: {e}")
                mount_path = volume.split(":")[1]
                host_path = volume.split(":")[0]
                requires_nfs = "no"
                if "TYCHO_ON_MINIKUBE" in os.environ:
                    if os.environ['TYCHO_ON_MINIKUBE'] == "True":
                        if host_path == "TYCHO_NFS":
                            continue
                        else:
                            self.volumes.append({
                                "volume_name": volume_name,
                                "claim_name": claim_name, 
                                "mount_path": mount_path,
                                "host_path": host_path
                            })
                else:
                    try:
                       if host_path == "TYCHO_NFS":
                          host_path = "nfs"
                          requires_nfs = "yes"
                       if host_path.split("/")[0] == "TYCHO_NFS":
                           host_path = host_path.split('/')[1]
                           requires_nfs = "yes"
                    except Exception as e:
                       print(f"Requires NFS ----> {requires_nfs}") 
                    self.volumes.append({
                        "requires_nfs": requires_nfs,
                        "volume_name": volume_name,
                        "claim_name": host_path, 
                        "disk_name": disk_name,
                        "mount_path": mount_path,
                    })
            return self.volumes
        except Exception as e:
            print(f"VOLUMES----> Do not exist {e}")
    
class Container:
    """ Invocation of an image in a specific infastructural context. """
    def __init__(self,
                 name,
                 image,
                 command=None,
                 env=None,
                 identity=None,
                 limits=None,
                 requests=None,
                 ports=[],
                 expose=[],
                 volumes=None):
        """ Construct a container.
        
            :param name: Name the running container will be given.
            :param image: Name of the image to use.
            :param command: Text of the command to run.
            :param env: Environment settings
            :type env: dict
            :param identity: UID of the user to run as.
            :type identity: int
            :param limits: Resource limits
            :type limits: dict
            :param requests: Resource requests
            :type limits: dict
            :param ports: Container ports to expose.
            :type ports: list of int
            :param volumes: List of volume mounts <host_path>:<container_path>
            :type volumes: list of str
        """
        self.name = name
        self.image = image
        self.identity = identity
        self.limits = Limits(**limits) if isinstance(limits, dict) else limits
        self.requests = Limits(**requests) if isinstance(requests, dict) else requests
        if isinstance(self.limits, list):
            self.limits = self.limits[0] # TODO - not sure why this is a list.
        self.ports = ports
        self.expose = expose
        self.command = command
        self.env = \
                   list(map(lambda v : list(map(lambda r: str(r), v.split('='))), env)) \
                   if env else []
                                                                             
        self.volumes = volumes

    def __repr__(self):
        return f"name:{self.name} image:{self.image} id:{self.identity} limits:{self.limits}"

class System:
    """ Distributed system of interacting containerized software. """
    def __init__(self, config, name, containers, services={}):
        """ Construct a new abstract model of a system given a name and set of containers.
        
            Serves as context for the generation of compute cluster specific artifacts.

            :param config: Configuration information.
            :type name: `Config`
            :param name: Name of the system.
            :type name: str
            :param containers: List of container specifications.
            :type containers: list of containers
        """
        self.config = config
        self.identifier = uuid.uuid4().hex
        self.system_name = name
        self.name = f"{name}-{self.identifier}"
        assert self.name is not None, "System name is required."
        containers_exist = len(containers) > 0
        none_are_null = not any([ c for c in containers if c == None ])
        assert containers_exist and none_are_null, "System container elements may not be null."
        self.containers = list(map(lambda v : Container(**v), containers)) \
                          if isinstance(containers[0], dict) else \
                             containers
        """ Construct a map of services. """
        self.services = {
            service_name : Service(**service_def)
            for service_name, service_def in services.items ()
        }
        for name, service in self.services.items ():
            service.name = f"{name}-{self.identifier}"
        self.volumes = Volumes(self.name, name, containers).process_volumes()    
        self.source_text = None

    def requires_network_policy (self):
        return any ([ len(svc.clients) > 0 for name, svc in self.services.items () ])
    
    def render (self, template, context={}):
        """ Supply this system as a context to a template.
        
            :param template: Template 
        """
        final_context = { "system" : self }
        for n, v in context.items ():
            final_context[n] = v
        generator = TemplateUtils (config=self.config)
        template = generator.render (template, context=final_context)
        logger.debug (f"--generated template: {template}")
        return template

    @staticmethod
    def parse (config, name, system, env={}, services={}):
        """ Construct a system model based on the input request.

            Parses a docker-compose spec into a system specification.
        
            :param name: Name of the system.
            :param system: Parsed docker-compose specification.
            :param env: Dictionary of settings.
            :param services: Service specifications - networking configuration.
        """
        containers = []
        if env:
            logger.debug ("applying environment settings.")
            system_template = yaml.dump (system)
            print (json.dumps(env,indent=2))
            system_rendered = TemplateUtils.render_text (
                template_text=system_template,
                context=env)
            logger.debug (f"applied settings:\n {system_rendered}")
            for system_render in system_rendered:
                system = system_render

        """ Model each service. """
        logger.debug (f"compose {system}")
        for cname, spec in system.get('services', {}).items ():
            """ Entrypoint may be a string or an array. Deal with either case."""
            ports = []
            expose = []
            entrypoint = spec.get ('entrypoint', '')
            if isinstance(entrypoint, str):
                entrypoint = entrypoint.split ()
            for p in spec.get('ports', []):
              if ':' in p:
                ports.append({
                  'containerPort': p.split(':')[1]
                })
              else:
                ports.append({
                  'containerPort': p
                })
            for e in spec.get('expose', []):
              expose.append({
                'containerPort': e
              })
            containers.append ({
                "name"    : cname,
                "image"   : spec['image'],
                "command" : entrypoint,
                "env"     : spec.get ('env', []),
                "limits"  : spec.get ('deploy',{}).get('resources',{}).get('limits',{}),
                "requests"  : spec.get ('deploy',{}).get('resources',{}).get('reservations',{}),
                "ports"   : ports,
                "expose"  : expose,
                "volumes"  : [ v for v in spec.get("volumes", []) ]
            })
        system_specification = {
            "config"     : config,
            "name"       : name,
            "containers" : containers
        }
        system_specification['services'] = services
        logger.debug (f"parsed-system: {json.dumps(system_specification, indent=2)}")
        system = System(**system_specification)
        system.source_text = yaml.dump (system)
        return system

    def __repr__(self):
        return f"name:{self.name} containers:{self.containers}"

class Service:
    """ Model network connectivity rules to the system. """
    def __init__(self, port=None, clients=[]):
        """ Construct a service object modeling network connectivity to a system. """
        self.port = port
        self.clients = list(map(lambda v: str(ipaddress.ip_network (v)), clients))
        self.name = None
        
    def __repr__(self):
        return json.dumps (
            f"service: {json.dumps({'port':self.port,'clients':self.clients}, indent=2)}")
