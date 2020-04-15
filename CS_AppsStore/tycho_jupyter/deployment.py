import os
import yaml
from tycho.client import TychoClientFactory
from tycho.client import TychoApps
#import time
import json

#from django.http import HttpResponseRedirect

def deploy(request):
    if "HTTP_REFERER" in request.META:
        url_referer = request.META["HTTP_REFERER"]
        system_url = url_referer.split("/")[2]
    try:
        client_factory = TychoClientFactory()
        client = client_factory.get_client()
        tycho_url = client.url
        print(f"TYCHO URL: {tycho_url}")
    except Exception as e:
        tycho_url = "http://localhost:5000/system"
        print(f"TYCHO URL: {tycho_url}")

    try:
        app = "jupyter-ds"
        tychoapps = TychoApps(app)
    except Exception as e:
        print(f"Exception: {e}")

    metadata = tychoapps.getmetadata()

    if 'System' in metadata.keys():
        structure = metadata['System']
        print(f"Structure: {structure}")
    if 'Settings' in metadata.keys():
        settings = metadata['Settings']
        print(f"Settings: {settings}")

    """ Load settings. """
    settings_dict = client.parse_env(settings)
    print(f"Settings Dict: {settings_dict}")

    username = request.META["REMOTE_USER"]

    request = {
            "name": "jupyter-ds",
            "username": request.META["REMOTE_USER"],
            "env": settings_dict,
            "system": structure,
            "services": {
                "jupyter-ds": {
                "port": settings_dict['HOST_PORT']
                }
             }
    }

    print("Sending this request to tycho client to start imagej app:")
    print(json.dumps(request))

    tycho_system = client.start(request)

    print(f"TYCHO SYSTEM: {tycho_system}")
    system_name = tycho_system.name.split("-")[0]
    identifier = tycho_system.identifier
    print(f"LOCAL SYSTEM_NAME: {system_name}")
    print(f"LOCAL SYSTEM IDENTIFIER: {identifier}")


    guid = tycho_system.identifier
    status = tycho_system.status
    services = tycho_system.services

    print(f"Service Jupyter: {services}")
    print(status)

    if status != 'success':
        raise Exception("Error encountered while starting jupyter-datascience service: " + status)

    for service in services:
        name = service.name
        print(f"SERVICE NAME: {name}")
        if name == 'jupyter-ds':
            ip_address = service.ip_address
            port = service.port
            port = settings_dict['HOST_PORT']
            print('ip_address: ' + ip_address)
            print('port: ' + str(port))
            break

    if ip_address == '' or ip_address == '--':
        raise Exception("ip_address is invalid: " + ip_address)

    if port == '' or port == '--':
        raise Exception("port is invalid: " + port)

    redirect_url = f"http://{system_url}/private/{app}/{username}/{identifier}/"
    print('redirecting to ' + redirect_url)
    return redirect_url
