from rest_framework.exceptions import APIException

class AuthorizationTokenUnavailable(APIException):
    status_code = 400
    default_detail = 'Authorization token not found.'
    default_code = 'bad_request'