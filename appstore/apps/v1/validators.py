from rest_framework import serializers


def memory_format_validator(value):
    valid_memory_unit = ('M', 'G', 'T', 'P', 'E')

    if not value.endswith(valid_memory_unit):
        raise serializers.ValidationError(f"Invalid memory unit {value}.\n"
                                          f"Valid memory units: {valid_memory_unit}")

