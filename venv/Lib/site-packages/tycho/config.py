import ipaddress
import json
import logging
import os
import yaml
import traceback
import re
from tycho.tycho_utils import Resource

logger = logging.getLogger (__name__)

class Config(dict): 
    """ Handle configuration for the system. """
    def __init__(self, config="conf/tycho.yaml"):
        """ Load the system configuration. """
        if isinstance(config, str):
            config_path = Resource.get_resource_path (config)
            logger.debug (f"loading config: {config_path}")
            with open(config_path, 'r') as f:
                self.conf = yaml.safe_load (f)
        elif isinstance(config, dict):
            self.conf = config
        else:
            raise ValueError

        """ Determine if we're on minikube. If so, share its ip address via
        the config. """
        logger.debug (f"loaded config: {json.dumps(self.conf,indent=2)}")
        if 'TYCHO_ON_MINIKUBE' in os.environ:
            ip = os.popen('minikube ip').read().strip ()
            if len(ip) > 0:
                try:
                    ipaddress.ip_address (ip)
                    logger.info (f"configuring minikube ip: {ip}")
                    self.conf['tycho']['compute']['platform']['kube']['ip'] = ip
                except ValueError as e:
                    logger.error ("unable to get minikube ip address")
                    traceback.print_exc (e)

    def __setitem__(self, key, val):
        self.conf.__setitem__(key, val)
    def __str__(self):
        return self.conf.__str__()
    def __getitem__(self, key):
        return self.conf.__getitem__(key)
    def get (self, key, default=None):
        return self.conf.get(key, default)
