import datetime
import json
import logging
import netifaces
import os
import string
import traceback
import yaml
from jinja2 import Template

logger = logging.getLogger (__name__)

class TemplateUtils:
    """ Utilities for generating text. """

    def __init__(self, config):
        self.config = config

    def render (self, template, context):
        """Render a template object given a context. """
        result=None
        template_path = None
        
        """ First, allow the user to override the default templates with custom templates.
            Check for a template with this name in the user provided paths. """
        alternate_paths = self.config['tycho']['templates']['paths']
        for path in alternate_paths:
            if os.path.exists (path):
                template_path = os.path.join (path, template)
                if os.path.exists (template_path):
                    logger.debug (f"using user supplied template: {template_path}")
                else:
                    template_path = None
            else:
                logger.warning (f"template path {path} is configured but does not exist.")

        if not template_path:
            """ Still no template. Look for it in the default design. """
            template_path = os.path.join (os.path.dirname (__file__), "template", template)
            if not os.path.exists (template_path):
                template_path = None

        if not template_path:
            raise ValueError (
                f"No template {template} found in default location or in {alternate_paths}")
        
        logger.debug (f"applying template {template_path}")
        with open(template_path, "r") as stream:
            template_text = stream.read ()
            result = TemplateUtils.render_text (template_text, context)
        return result

    @staticmethod
    def render_text (template_text, context):
        """ Render the text of a template given a context. """
        #logger.debug (template_text)
        #logger.debug (context)
        template = Template (template_text)
        template.globals['now'] = datetime.datetime.utcnow
        text = template.render (**context)
        logger.debug (f"TemplateUtils.render_text - {text}")
        return yaml.load_all (text, Loader=yaml.SafeLoader)

    @staticmethod
    def render_string(s,context):
        tmpl = Template(s)
        tmpl.globals['now'] = datetime.datetime.utcnow
        return tmpl.render(context)

    @staticmethod
    def apply_environment (environment, text):
        """ Given an environment configuration consisting of lines of Bash style variable assignemnts,
        parse the variables and apply them to the given text."""
        resolved = text
        if environment:
            mapping = {
                line.split("=", maxsplit=1)[0] : line.split("=", maxsplit=1)[1]
                for line in environment.split ("\n") if '=' in line
            }
            resolved = string.Template(text).safe_substitute (**mapping)
            logger.debug (f"environment={json.dumps (mapping, indent=2)}")
            logger.debug (resolved)
        return resolved

    @staticmethod
    def trunc (a_string, max_len=80):
        return (a_string[:max_len] + '..') if len(a_string) > max_len else a_string

class NetworkUtils:
    @staticmethod
    def get_client_ip (request, debug=False):
        """ Get the IP address of the client. Account for requests from proxies. 
        In debug mode, ignore loopback and try to get an IP from a n interface."""
        ip_addr = request.remote_addr
        if request.headers.getlist("X-Forwarded-For"):
            ip_addr = request.headers.getlist("X-Forwarded-For")[0]
        if debug:
            interface = netifaces.ifaddresses ('en0')
            ip_addr = interface[2][0]['addr']
        logger.debug (f"(debug mode ip addr:)--> {ip_addr}")
        return ip_addr

class Resource:
    @staticmethod
    def get_resource_path(resource_name):
       # Given a string resolve it to a module relative file path unless it is already an absolute path.
        resource_path = resource_name
        if not resource_path.startswith (os.sep):
            resource_path = os.path.join (os.path.dirname (__file__), resource_path)
        return resource_path
    
    @staticmethod
    def load_json (path):
        result = None
        with open (path, 'r') as stream:
            result = json.loads (stream.read ())
        return result

    @staticmethod
    def load_yaml (path):
        result = None
        with open (path, 'r') as stream:
            result = yaml.safe_load (stream.read ())
        return result
    
    def get_resource_obj (self, resource_name, format=None):
        # TODO: Fix bug where format could be different than resource's file extension in file name
        result = None
        if not format:
            if resource_name.endswith ('.yaml'):
                format = 'yaml'
            else:
                format = 'json'
        path = Resource.get_resource_path (resource_name)
        if os.path.exists (path):
            m = {
                'json' : Resource.load_json,
                'yaml' : Resource.load_yaml
            }
            if format in m:
                result = m[format](path)
        return result
