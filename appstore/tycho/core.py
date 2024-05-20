from tycho.config import Config
from tycho.factory import ComputeFactory
from tycho.factory import supported_backplanes
from tycho.model import System, ModifySystem

class Tycho: 
    """ An organizing abstraction for the Tycho system. 

        Tycho adds a layer of system architecture and policy support to 
        cloud native container orchestration platforms. It's true you can do just
        about anything with the Kubernetes API. Tycho let's teams design, decide,
        automate, test, and enforce what should be done.

    """
    
    def __init__(self,
                 backplane="kubernetes",
                 config="conf/tycho.yaml"):
        """ Construct a Tycho component. 
        
            :param backplane: The name of the compute back end. Analogous to a compiler's
                              code emitter, the backplane's concern is to project a system
                              abstract syntax tree (AST) into a compute fabric specific 
                              structure.
            :param config: A configuration file for the system.
        """
        self.backplane = backplane
        self.config = Config (config)
        self.compute = ComputeFactory.create_compute (self.config)
        
    def get_compute (self):
        """ Get the Tycho API for the compute fabric. 
    
            :returns: A compute fabric code emitter implementation specified to the constructor.
        """
        return self.compute

    def parse (self, request):
        """ Parse a request to construct an abstract syntax tree for a system.
        
            :param request: JSON object formatted to contain name, structure, env, and
                            service elements. Name is a string. Structue is the JSON
                            object resulting from loading a docker-compose.yaml. Env
                            is a JSON dictionary mapping environment variables to
                            values. These will be substituted into the specification.
                            Services is a JSON object representing which containers and
                            ports to expose, and other networking rules.
            :returns: `.System`
        """
        return System.parse (
            config=self.config,
            name=request['name'],
            principal=request.get('principal'),
            system=request['system'],
            service_account=request.get('serviceaccount', 'default'),
            env=request.get ('env', {}),
            services=request.get ('services', {}))

    def parse_modify(self, request):
        """ Parse a request into a class representation of metadata and specs of a system to be modified.

            :param request: JSON object formatted to contain guid, labels, resources.
                            GUID is a hexadecimal string of UUID representing a system.
                            Labels is a dictionary of label and label-name as key-value pairs.
                            Resources is a dictionary of cpu and memory keys, with corresponding values.
                            Can optionally pass a config.
            :returns: An instance of `tycho.model.ModifySystem`
        """
        return ModifySystem.parse_modify(
            config=self.config,
            guid=request.get("tycho-guid", None),
            labels=request.get("labels", {}),
            cpu=request.get("cpu", None),
            memory=request.get("memory", None))

    @staticmethod
    def is_valid_backplane (backplane):
        """ Determine if the argument is a valid backplane. """
        return ComputeFactory.is_valid_backplane (backplane)
    
    @staticmethod
    def supported_backplanes ():
        return list(supported_backplanes)