import os
import yaml
from tycho.client import TychoClientFactory
from tycho.client import TychoApps
import json

def deploy(request):
    printf("Enter cloudtop_imagej/deployment.py::deploy(request)")
    if "HTTP_REFERER" in request.META:
        url_referer = request.META["HTTP_REFERER"]
        system_url = url_referer.split("/")[2]
        print(f"SYSTEM URL from Http_Referer: {system_url}")

    try:
        client_factory = TychoClientFactory()
        print(f"CLIENT FACTORY: {client_factory}")
        client = client_factory.get_client()
        tycho_url = client.url
        print(f"TYCHO URL: {tycho_url}")
    except Exception as e:
        tycho_url = "http://localhost:5000/system"
        print(f"TYCHO URL: {tycho_url}")

    try:
        app = "imagej"
        tychoapps = TychoApps(app)
    except Exception as e:
        print(f"Exception: {e}")

    metadata = tychoapps.getmetadata()

    if 'System' in metadata.keys():
        structure = metadata['System']
        print(f"Structure: {structure}")
    if 'Settings' in metadata.keys():
        settings = metadata['Settings']
        print(f"settings: {settings}")

    """ Load settings. """
    settings_dict = client.parse_env(settings)
    print(f"Settings Dict: {settings_dict}")

    """ Load docker-compose file for CloudTop consisting of system spec """
    username = request.META["REMOTE_USER"]

    request = {
            "name": "imagej",
            "username": request.META["REMOTE_USER"],
            "env": settings_dict,
            "system": structure,
            "services": {
                "imagej": {
                "port": settings_dict['HOST_PORT']
                }
             }
    }

    print("Request sent to tycho client start to start imagej client app:")
    print(json.dumps(request))

    tycho_system = client.start(request)
    print(f"TYCHO SYSTEM: {tycho_system.name}, {tycho_system.identifier}")
    system_name = tycho_system.name.split("-")[0]
    identifier = tycho_system.identifier

    status = tycho_system.status
    services = tycho_system.services

    print(f"Service Imagej: {services}")

    if status != 'success':
        raise Exception("Error encountered while starting ImageJ service: " + status)

    for service in services:
        name = service.name
        if name == 'imagej':
            ip_address = service.ip_address
            port = service.port
            port = settings_dict['HOST_PORT']
            print('ip_address: ' + ip_address)
            print('port: ' + str(port))
            break

    if ip_address == '' or ip_address == '--':
        raise Exception("imagej ip_address is invalid: " + ip_address)

    if port == '' or port == '--':
        raise Exception("imagej port is invalid: " + port)

    redirect_url = f"http://{system_url}/private/{system_name}/{username}/{identifier}/"
    print('redirecting to ' + redirect_url)
    return redirect_url
