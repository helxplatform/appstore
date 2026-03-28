"""Tests for kube.labels helpers."""

from kube import labels as L


class TestStandardLabels:
    def test_minimal(self):
        lbl = L.standard_labels(instance_id="abc123")
        assert lbl[L.EXECUTOR] == L.EXECUTOR_VALUE
        assert lbl[L.ID] == "abc123"
        assert L.APP_NAME not in lbl

    def test_full(self):
        lbl = L.standard_labels(
            instance_id="abc",
            app_name="jupyter",
            username="alice",
            app_class_name="JupyterLab",
            instance_name="jupyter-alice",
        )
        assert lbl[L.APP_NAME] == "jupyter"
        assert lbl[L.USERNAME] == "alice"
        assert lbl[L.APP_CLASS_NAME] == "JupyterLab"
        assert lbl[L.INSTANCE_NAME] == "jupyter-alice"


class TestSelectors:
    def test_by_id(self):
        s = L.selector_by_id("deadbeef")
        assert s == "helx.renci.org/id=deadbeef"

    def test_by_username(self):
        s = L.selector_by_username("alice")
        assert s == "helx.renci.org/username=alice"

    def test_all_managed(self):
        s = L.selector_all_managed()
        assert s == "executor=helxapp-controller"
