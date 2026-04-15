"""Tests for RegistryLoader — file I/O."""

import os
import tempfile

import pytest
import yaml

from helx.registry.loader import RegistryLoader


@pytest.fixture
def loader():
    return RegistryLoader()


class TestLoadConfig:
    def test_load_config(self, loader, tmp_path):
        cfg = {"contexts": {"common": {"apps": {"a": {"name": "A"}}}}}
        path = tmp_path / "registry.yaml"
        path.write_text(yaml.dump(cfg))
        result = loader.load_config(str(path))
        assert result["contexts"]["common"]["apps"]["a"]["name"] == "A"

    def test_load_config_empty(self, loader, tmp_path):
        path = tmp_path / "empty.yaml"
        path.write_text("")
        result = loader.load_config(str(path))
        assert result == {}


class TestLoadSpec:
    def test_renders_jinja2(self, loader, tmp_path):
        compose = (
            "services:\n"
            "  web:\n"
            "    image: {{ registry }}/myapp:latest\n"
        )
        path = tmp_path / "docker-compose.yaml"
        path.write_text(compose)
        result = loader.load_spec(str(path), {"registry": "containers.renci.org"})
        assert result["services"]["web"]["image"] == "containers.renci.org/myapp:latest"

    def test_plain_yaml(self, loader, tmp_path):
        compose = {"services": {"web": {"image": "nginx", "ports": ["80:80"]}}}
        path = tmp_path / "docker-compose.yaml"
        path.write_text(yaml.dump(compose))
        result = loader.load_spec(str(path), {})
        assert result["services"]["web"]["image"] == "nginx"

    def test_go_template_preserved(self, loader, tmp_path):
        """Go template expressions must survive Jinja2 unchanged."""
        compose = (
            "services:\n"
            "  app:\n"
            "    image: myapp:latest\n"
            "    command:\n"
            "      - --user={{ .system.UserName }}\n"
        )
        path = tmp_path / "docker-compose.yaml"
        path.write_text(compose)
        result = loader.load_spec(str(path), {})
        assert result["services"]["app"]["command"][0] == "--user={{ .system.UserName }}"

    def test_go_template_in_path_preserved(self, loader, tmp_path):
        """Dotted paths like .filebrowser/db must not cause parse errors."""
        compose = (
            "services:\n"
            "  fb:\n"
            "    image: filebrowser:latest\n"
            "    command:\n"
            "      - --database=/home/{{ .system.UserName }}/.filebrowser/filebrowser.db\n"
        )
        path = tmp_path / "docker-compose.yaml"
        path.write_text(compose)
        result = loader.load_spec(str(path), {})
        cmd = result["services"]["fb"]["command"][0]
        assert cmd == "--database=/home/{{ .system.UserName }}/.filebrowser/filebrowser.db"

    def test_jinja2_and_go_templates_coexist(self, loader, tmp_path):
        """Jinja2 vars are resolved; Go templates are preserved side-by-side."""
        compose = (
            "services:\n"
            "  app:\n"
            "    image: {{ registry }}/app:latest\n"
            "    command:\n"
            "      - --user={{ .system.UserName }}\n"
        )
        path = tmp_path / "docker-compose.yaml"
        path.write_text(compose)
        result = loader.load_spec(str(path), {"registry": "containers.renci.org"})
        assert result["services"]["app"]["image"] == "containers.renci.org/app:latest"
        assert result["services"]["app"]["command"][0] == "--user={{ .system.UserName }}"


class TestLoadSettings:
    def test_reads_env_file(self, loader, tmp_path):
        spec_path = tmp_path / "app" / "docker-compose.yaml"
        spec_path.parent.mkdir()
        spec_path.write_text("services: {}")
        env_path = tmp_path / "app" / ".env"
        env_path.write_text("FOO=bar\nBAZ=qux\n")
        result = loader.load_settings(str(spec_path))
        assert "FOO=bar" in result
        assert "BAZ=qux" in result

    def test_missing_env_returns_empty(self, loader, tmp_path):
        spec_path = tmp_path / "app" / "docker-compose.yaml"
        spec_path.parent.mkdir()
        spec_path.write_text("services: {}")
        result = loader.load_settings(str(spec_path))
        assert result == ""
