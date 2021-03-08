import logging

from rest_framework import serializers
from .models import Service, App, ResourceRequest, ServiceSpec
from .validators import memory_format_validator

logger = logging.getLogger(__name__)


class ServiceSerializer(serializers.Serializer):
    name = serializers.CharField(required=True)
    docs = serializers.CharField(required=True)
    sid = serializers.CharField(required=True)
    fqsid = serializers.CharField(required=True)
    creation_time = serializers.CharField(
        required=True
    )  # serializers.DateTimeField(format='iso-8601') - date error from tycho
    cpu = serializers.IntegerField(required=True)
    gpu = serializers.IntegerField(default=0)
    # TODO switch to Float potentially, or validator
    memory = serializers.CharField(required=True)


class AppDetailSerializer(serializers.Serializer):
    name = serializers.CharField(required=True)
    app_id = serializers.CharField(required=True)
    description = serializers.CharField(required=True)
    detail = serializers.CharField(required=True)
    docs = serializers.CharField(required=True)
    spec = serializers.CharField(required=True)
    cpu = serializers.IntegerField(required=True)
    gpu = serializers.IntegerField(default=0)
    memory = serializers.CharField(required=True, validators=[memory_format_validator])


class AppSerializer(serializers.Serializer):
    serializers.DictField(child=AppDetailSerializer())


class ResourceSerializer(serializers.Serializer):
    app_id = serializers.CharField(required=True)
    cpu = serializers.IntegerField(required=True)
    gpu = serializers.IntegerField(default=0)
    memory = serializers.CharField(required=True, validators=[memory_format_validator])

    def create(self, validated_data):
        return ResourceRequest(**validated_data)


class ServiceSpecSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    app_id = serializers.CharField(required=True)
    name = serializers.CharField(required=True)
    host = serializers.CharField(required=True)
    resources = serializers.DictField(required=True)
    url = serializers.CharField(required=True)
    protocol = serializers.CharField(required=True)


class ServiceIdentifierSerializer(serializers.Serializer):
    sid = serializers.CharField(required=True)


class UserSerializer(serializers.Serializer):
    REMOTE_USER = serializers.CharField(required=True)
    ACCESS_TOKEN = serializers.CharField(required=True)
