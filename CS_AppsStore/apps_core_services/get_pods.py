from tycho.client import TychoClientFactory
import requests


def get_pods_services(request):
    try:
        client_factory = TychoClientFactory()
        client = client_factory.get_client()
        tycho_url = client.url
        print(f"TYCHO URL: {tycho_url}")
    except Exception as e:
        tycho_url = "http://localhost:5000/system"
        print(f"TYCHO URL: {tycho_url}")

    request_pods = {}
    request_pods['username'] = request.user.username

    tycho_status = client.status(request_pods)
    print(tycho_status)
    return tycho_status

def delete_pods(request, sid):
    try:
        client_factory = TychoClientFactory()
        client = client_factory.get_client()
        tycho_url = client.url
        print(f"TYCHO URL: {tycho_url}")
    except Exception as e:
        tycho_url = "http://localhost:5000/system"
        print(f"TYCHO URL: {tycho_url}")

    names = [sid]
    tycho_status = client.down(names=names)
    print(tycho_status)
    return tycho_status