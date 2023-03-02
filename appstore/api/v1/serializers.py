import logging

from rest_framework import serializers
from .models import ResourceRequest
from .validators import memory_format_validator

logger = logging.getLogger(__name__)


class InstanceModifySerializer(serializers.Serializer):
    labels = serializers.DictField(
        child=serializers.CharField(), required=False, allow_empty=False
    )
    cpu = serializers.CharField(required=False, allow_blank=False)
    memory = serializers.CharField(
        validators=[memory_format_validator], required=False, allow_blank=False
    )


class InstanceSerializer(serializers.Serializer):
    name = serializers.CharField()
    docs = serializers.CharField()
    aid = serializers.CharField(allow_null=True)
    sid = serializers.CharField()
    fqsid = serializers.CharField()
    workspace_name = serializers.CharField(allow_blank=True)
    creation_time = (
        serializers.CharField()
    )  # serializers.DateTimeField(format='iso-8601') - date error from tycho
    cpus = serializers.FloatField()
    gpus = serializers.IntegerField(default=0)
    # TODO switch to Float potentially, or validator
    memory = serializers.CharField()
    url = serializers.CharField()
    status = serializers.CharField()


class AppDetailSerializer(serializers.Serializer):
    name = serializers.CharField()
    app_id = serializers.CharField()
    description = serializers.CharField()
    detail = serializers.CharField()
    docs = serializers.CharField()
    spec = serializers.CharField()
    count = serializers.IntegerField()
    minimum_resources = serializers.DictField()
    maximum_resources = serializers.DictField()


class AppSerializer(serializers.Serializer):
    serializers.DictField(child=AppDetailSerializer())


class ResourceSerializer(serializers.Serializer):
    app_id = serializers.CharField()
    cpus = serializers.FloatField()
    gpus = serializers.IntegerField(default=0)
    memory = serializers.CharField(validators=[memory_format_validator])

    def create(self, validated_data):
        return ResourceRequest(**validated_data)


class InstanceSpecSerializer(serializers.Serializer):
    username = serializers.CharField()
    app_id = serializers.CharField()
    sid = serializers.CharField()
    name = serializers.CharField()
    host = serializers.CharField()
    resources = serializers.DictField()
    url = serializers.CharField()
    protocol = serializers.CharField()


class InstanceIdentifierSerializer(serializers.Serializer):
    sid = serializers.CharField()


class UserSerializer(serializers.Serializer):
    REMOTE_USER = serializers.CharField()
    ACCESS_TOKEN = serializers.CharField(required=False, allow_null=True)
    SESSION_TIMEOUT = serializers.IntegerField()


class LoginProviderSerializer(serializers.Serializer):
    name = serializers.CharField()
    url = serializers.CharField()


class AppContextSerializer(serializers.Serializer):
    brand = serializers.CharField()
    title = serializers.CharField()
    logo_url = serializers.CharField()
    color_scheme = serializers.DictField()
    links = serializers.ListField(required=False, allow_null=True)
    capabilities = serializers.ListField()
    env = serializers.DictField()


class EmptySerializer(serializers.Serializer):
    pass
