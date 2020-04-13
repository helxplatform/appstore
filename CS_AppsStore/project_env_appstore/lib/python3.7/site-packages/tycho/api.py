import argparse
import ipaddress
import json
import jsonschema
import logging
import netifaces
import os
import requests
import sys
import traceback
import yaml
from flasgger import Swagger
from flask import Flask, jsonify, g, Response, request
from flask_restful import Api, Resource
from flask_cors import CORS
from tycho.core import Tycho
from tycho.tycho_utils import NetworkUtils

"""
Defines the Tycho API

Provides endpoints for creating, monitoring, and deleting distributed systems of cloud native
containers running on abstracted compute fabrics. 
 
"""
logger = logging.getLogger (__name__)

app = Flask(__name__)

""" Enable CORS. """
api = Api(app)
CORS(app)
debug=False

""" Load the schema. """
schema_file_path = os.path.join (
    os.path.dirname (__file__),
    'api-schema.yaml')
template = None
with open(schema_file_path, 'r') as file_obj:
    template = yaml.load(file_obj)

""" Describe the API. """
app.config['SWAGGER'] = {
    'title': 'Tycho Compute API',
    'description': 'An API, compiler, and executor for cloud native distributed systems.',
    'uiversion': 3
}

swagger = Swagger(app, template=template)

backplane = None
def tycho ():
    if not hasattr(g, 'tycho'):
        g.tycho = Tycho (backplane=backplane)
    return g.tycho
    
class TychoResource(Resource):
    """ Base class handler for Tycho API requests. """
    def __init__(self):
        self.specs = {}
        
    """ Functionality common to Tycho services. """
    def validate (self, request, component):
        """ Validate a request against the schema. """
        if not self.specs:
            with open(schema_file_path, 'r') as file_obj:
                self.specs = yaml.load(file_obj)
        to_validate = self.specs["components"]["schemas"][component]
        try:
            app.logger.debug (f"--:Validating obj {json.dumps(request.json, indent=2)}")
            app.logger.debug (f"  schema: {json.dumps(to_validate, indent=2)}")            
            jsonschema.validate(request.json, to_validate)
        except jsonschema.exceptions.ValidationError as error:
            app.logger.error (f"ERROR: {str(error)}")
            traceback.print_exc (error)
            abort(Response(str(error), 400))

    def create_response (self, result=None, status='success', message='', exception=None):
        """ Create a response. Handle formatting and modifiation of status for exceptions. """
        if exception:
            traceback.print_exc ()
            status='error'
            exc_type, exc_value, exc_traceback = sys.exc_info()
            result = {
                'error' : repr(traceback.format_exception(exc_type, exc_value, exc_traceback))
            }
        return {
            'status'  : status,
            'result'  : result,
            'message' : message
        }
            
class StartSystemResource(TychoResource):
    """ Parse, model, emit orchestrator artifacts and execute a system. """
    
    """ System initiation. """
    def post(self):
        """
        Start a system based on a specification on the compute fabric.
        
        The specification is a docker-compose yaml parsed into a JSON object.
        ---
        tag: start
        description: Start a system on the compute fabric.
        requestBody:
            description: System start message.
            required: true
            content:
                application/json:
                    schema:
                        $ref: '#/components/schemas/System'
        responses:
            '200':
                description: Success
                content:
                    text/plain:
                        schema:
                            type: string
                            example: "Successfully validated"
            '400':
                description: Malformed message
                content:
                    text/plain:
                        schema:
                            type: string

        """
        response = {}
        try:
            app.logger.info (f"start-system: {json.dumps(request.json, indent=2)}")
            self.validate (request, component="System")
            system = tycho().parse (request.json)
            response = self.create_response (
                result=tycho().get_compute().start (system),
                message=f"Started system {system.name}")
        except Exception as e:
            response = self.create_response (
                exception=e,
                message=f"Failed to create system.")
        return response
    
class DeleteSystemResource(TychoResource):
    """ System termination. Given a GUID for a Tycho system, use Tycho core to eliminate all
    components comprising the running system."""
    def post(self):
        """
        Delete a system based on a name.
        ---
        tag: start
        description: Delete a system on the compute fabric.
        requestBody:
            description: System start message.
            required: true
            content:
                application/json:
                    schema:
                        $ref: '#/components/schemas/DeleteRequest'
        responses:
            '200':
                description: Success
                content:
                    application/json:
                        schema:
                            type: string
                            example: "Successfully validated"
            '400':
                description: Malformed message
                content:
                    text/plain:
                        schema:
                            type: string

        """
        response = {}
        system_name=None
        try:
            logging.debug (f"delete-request: {json.dumps(request.json, indent=2)}")
            self.validate (request, component="DeleteRequest")
            system_name = request.json['name']
            response = self.create_response (
                result=tycho().get_compute().delete (system_name),
                message=f"Deleted system {system_name}")
        except Exception as e:
            response = self.create_response (
                exception=e,
                message=f"Failed to delete system {system_name}.")
        return response

class StatusSystemResource(TychoResource):
    """ Status executing systems. Given a GUID (or not) determine system status. """
    def post(self):
        """
        Status running systems.
        ---
        tag: start
        description: Status running systems.
        requestBody:
            description: List systems.
            required: true
            content:
                application/json:
                    schema:
                        $ref: '#/components/schemas/StatusRequest'
        responses:
            '200':
                description: Success
                content:
                    application/json:
                        schema:
                            type: string
                            example: "Successfully validated"
            '400':
                description: Malformed message
                content:
                    text/plain:
                        schema:
                            type: string

        """
        response = {}
        try:
            logging.debug (f"list-request: {json.dumps(request.json, indent=2)}")
            self.validate (request, component="StatusRequest") 
            system_name = request.json.get('name', None)
            response = self.create_response (
                result=tycho().get_compute().status (system_name),
                message=f"Get status for system {system_name}")
        except Exception as e:
            response = self.create_response (
                exception=e,
                message=f"Failed to get system status.")
        print (json.dumps (response, indent=2))
        return response

""" Register endpoints. """
api.add_resource(StartSystemResource, '/system/start')
api.add_resource(StatusSystemResource, '/system/status')
api.add_resource(DeleteSystemResource, '/system/delete')

if __name__ == "__main__":
   parser = argparse.ArgumentParser(description='Tycho Distributed Compute API')
   parser.add_argument('-b', '--backplane', help='Compute backplane type.', default="kubernetes")
   parser.add_argument('-p', '--port',  type=int, help='Port to run service on.', default=5000)
   parser.add_argument('-d', '--debug', help="Debug log level.", default=False, action='store_true')

   args = parser.parse_args ()

   """ Configure the compute back end. """
   if not Tycho.is_valid_backplane (args.backplane):
       print (f"Unrecognized backplane value: {args.backplane}.")
       print (f"Supported backplanes: {Tycho.supported_backplanes()}")
       parser.print_help ()
       sys.exit (1)
   backplane = args.backplane
   if args.debug:
       debug = True
       logging.basicConfig(level=logging.DEBUG)
   app.run(debug=args.debug)
   app.run(host='0.0.0.0', port=args.port, debug=True, threaded=True)
