"""Tests for the volume DSL parser."""

import pytest

from helx.kube.exceptions import VolumeDSLError
from helx.kube.volumes import parse_volume_dsl, parse_volumes_map


class TestParseVolumeDSL:
    def test_simple_pvc(self):
        v = parse_volume_dsl("home", "myhome:/home/user")
        assert v.scheme == "pvc"
        assert v.source == "myhome"
        assert v.mount_path == "/home/user"
        assert v.sub_path is None
        assert v.access_modes == ["ReadWriteOnce"]
        assert v.retain is False

    def test_explicit_pvc_scheme(self):
        v = parse_volume_dsl("data", "pvc://shared-data:/data")
        assert v.scheme == "pvc"
        assert v.source == "shared-data"
        assert v.mount_path == "/data"

    def test_rwx_option(self):
        v = parse_volume_dsl("home", "myhome:/home/user,rwx")
        assert v.access_modes == ["ReadWriteMany"]

    def test_rox_option(self):
        v = parse_volume_dsl("ro", "mydata:/data,rox")
        assert v.access_modes == ["ReadOnlyMany"]

    def test_rwop_option(self):
        v = parse_volume_dsl("scratch", "s:/tmp,rwop")
        assert v.access_modes == ["ReadWriteOncePod"]

    def test_retain_option(self):
        v = parse_volume_dsl("home", "myhome:/home/user,retain")
        assert v.retain is True

    def test_size_option(self):
        v = parse_volume_dsl("big", "big-vol:/data,size=50Gi")
        assert v.storage == "50Gi"

    def test_storage_class_option(self):
        v = parse_volume_dsl("fast", "fast-vol:/data,storageClass=ssd")
        assert v.storage_class == "ssd"

    def test_ro_option(self):
        v = parse_volume_dsl("ref", "ref-data:/ref,ro")
        assert v.read_only is True

    def test_sub_path(self):
        v = parse_volume_dsl("scratch", "scratch-vol:/tmp/scratch#mysubdir")
        assert v.sub_path == "mysubdir"

    def test_combined_options(self):
        v = parse_volume_dsl(
            "home", "alice-home:/home/alice,rwx,retain,size=10Gi"
        )
        assert v.access_modes == ["ReadWriteMany"]
        assert v.retain is True
        assert v.storage == "10Gi"

    def test_nfs_scheme(self):
        v = parse_volume_dsl("cache", "nfs:///nfs-server/cache:/mnt/cache")
        assert v.scheme == "nfs"
        assert v.mount_path == "/mnt/cache"

    def test_invalid_dsl_raises(self):
        with pytest.raises(VolumeDSLError):
            parse_volume_dsl("bad", "no-colon-here")

    def test_unknown_option_raises(self):
        with pytest.raises(VolumeDSLError, match="Unknown volume option"):
            parse_volume_dsl("x", "vol:/data,bogus")

    def test_to_dsl_string_roundtrip(self):
        v = parse_volume_dsl("home", "mypvc:/home,rwx,retain,size=5Gi")
        dsl = v.to_dsl_string()
        assert "mypvc:/home" in dsl
        assert "rwx" in dsl
        assert "retain" in dsl
        assert "size=5Gi" in dsl

    def test_to_dsl_string_with_subpath(self):
        v = parse_volume_dsl("data", "vol:/data#sub,ro")
        dsl = v.to_dsl_string()
        assert "vol:/data#sub" in dsl
        assert "ro" in dsl


class TestParseVolumesMap:
    def test_multiple(self):
        vols = parse_volumes_map(
            {
                "home": "alice-home:/home/alice,rwx,retain",
                "data": "shared-data:/data,size=50Gi,rwx",
            }
        )
        assert len(vols) == 2
        names = {v.volume_id for v in vols}
        assert names == {"home", "data"}
