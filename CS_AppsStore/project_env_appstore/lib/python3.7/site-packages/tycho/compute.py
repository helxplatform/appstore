import argparse
import json
import logging
import os
import sys
import threading
import traceback
import yaml

logger = logging.getLogger (__name__)

class Compute:
    """ Abstraction of a compute cluster. 

    We start with three primitives: start, status, and delete. Start takes a JSON object
    including (a) a docker-compose formatted description of a cloud native distributed system (b) the contents of an .env file accompanying a docker-compose.yaml including enviroment specific settings, and (c) additional metadata.
    
    """
    
    def start (self, system, namespace="default"):
        """ Given a system definition, start a distributed system.
        
            In docker port mapping pairs of the form <host_port>:<container_port>, we ignore 
            the host port. Tycho is designed to start many instances of an application and dynamic
            port allocation is assumed.

            Volume mounts of the form <host_path>:<container_path> will make a platform specific
            mapping of host_path. The general request format is::

                {
                   "name"   : <name of the system>,
                   "env"    : <text of .env environment variables>,
                   "system" : <JSON of a docker-compose yaml>
                }

            Responses contain status, message, and result elements.::

                {
                  "status": "success",
                  "result": {
                    "name": "nginx-7703f9cbf8f34caf8bc64e84384b7f1f",
                    "sid": "7703f9cbf8f34caf8bc64e84384b7f1f",
                    "containers": {
                      "nginx": {
                        "port": 30306
                      }
                    }
                  },
                  "message": "Started system nginx-7703f9cbf8f34caf8bc64e84384b7f1f"
                }

            :param system: docker-compose formatted specification of a distributed system.
            :type json: A JSON object structured as:
            :param namespace: Namespace. May not be supported by underlying compute fabric.
            :type namespace: string
            :return: Returns a JSON object including status, message, and result. Result is a dictionary containing details of the creatd object including name, system id (sid), and port mappings for each exposed service.

        """
        pass
    def delete (self, guid, namespace="default"):
        """ Delete a distributed system.
        
            Delete all generated artifacts in the underlying system.

            An example response::
         
                {
                  "status": "success",
                  "result": {},
                  "message": "Deleted system 82a9b5dc7d7c40c69ac05e3fb0f4df86"
                }

            :param guid: Globally unique identifier of the system, as returned by start.
            :type guid: string
            :param namespace: Namespace. May not be supported by underlying compute fabric.
            :type namespace: string
        """
        pass
    def status (self, guid=None, namespace="default"):
        """ Get status on running components of the system.

            Provided with a GUID, return status on matching components.

            Without a GUID, return data on all running components.

            An example response::

                {
                  "status": "success",
                  "result": [{
                    "name": "nginx-7703f9cbf8f34caf8bc64e84384b7f1f",
                    "sid": "7703f9cbf8f34caf8bc64e84384b7f1f",
                    "port": "30306"
                  }],
                  "message": "Get status for system None"
                }

            :param guid: GUID returned by start for a system.
            :param namespace: Namespace. May not be supported by underlying compute fabric.
        
        """
        pass
