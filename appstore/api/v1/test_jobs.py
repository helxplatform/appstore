"""Tests for the /api/v1/jobs/ launch contract: serializer validation and the
V1Job that KubernetesCompute.start_job builds.

Deliberately avoids importing views.py, which builds a live Tycho context (and
therefore needs a kubeconfig) at import time. Run on its own with:

    SECRET_KEY=x DEV_PHASE=stub DJANGO_SETTINGS_MODULE=appstore.settings.helx_settings \
        python manage.py test api.v1.test_jobs
"""

from unittest.mock import MagicMock

from django.test import SimpleTestCase, override_settings

from tycho.kube import KubernetesCompute

from .serializers import JobLaunchSerializer


BASE_REQUEST = {
    "image": "mismplatform/pi-envagent:k8s-test",
    "name": "envbuild-6f1c2a9b",
    "identifier": "a3f9" * 8,
}


class TestJobLaunchSerializer(SimpleTestCase):
    def test_new_fields_default_to_off(self):
        s = JobLaunchSerializer(data=BASE_REQUEST)
        self.assertTrue(s.is_valid(), s.errors)
        data = s.validated_data
        self.assertIsNone(data["service_account"])
        self.assertEqual(data["env_from"], [])
        self.assertEqual(data["secret_mounts"], [])
        self.assertIsNone(data["ttl_seconds_after_finished"])
        self.assertIsNone(data["security_context"])

    @override_settings(JOB_ALLOWED_SERVICE_ACCOUNTS=["envbuild"])
    def test_allowlisted_service_account_accepted(self):
        s = JobLaunchSerializer(data={**BASE_REQUEST, "service_account": "envbuild"})
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data["service_account"], "envbuild")

    @override_settings(JOB_ALLOWED_SERVICE_ACCOUNTS=["envbuild"])
    def test_unlisted_service_account_rejected(self):
        s = JobLaunchSerializer(data={**BASE_REQUEST, "service_account": "cluster-admin"})
        self.assertFalse(s.is_valid())
        self.assertIn("service_account", s.errors)

    @override_settings(JOB_ALLOWED_SERVICE_ACCOUNTS=[])
    def test_empty_allowlist_rejects_any_service_account(self):
        s = JobLaunchSerializer(data={**BASE_REQUEST, "service_account": "envbuild"})
        self.assertFalse(s.is_valid())

    def test_env_from_kind_validated(self):
        s = JobLaunchSerializer(data={**BASE_REQUEST, "env_from": [{"kind": "pod", "name": "x"}]})
        self.assertFalse(s.is_valid())
        self.assertIn("env_from", s.errors)

    def test_negative_ttl_rejected(self):
        s = JobLaunchSerializer(data={**BASE_REQUEST, "ttl_seconds_after_finished": -1})
        self.assertFalse(s.is_valid())

    def test_full_envbuild_request_valid(self):
        with override_settings(JOB_ALLOWED_SERVICE_ACCOUNTS=["envbuild"]):
            s = JobLaunchSerializer(data={
                **BASE_REQUEST,
                "service_account": "envbuild",
                "env_from": [
                    {"kind": "configmap", "name": "envbuild-tuning", "optional": True},
                    {"kind": "secret", "name": "envbuild-llm"},
                ],
                "secret_mounts": [{
                    "secret": "envbuild-registry-auth",
                    "mount_path": "/home/node/.docker",
                    "items": {".dockerconfigjson": "config.json"},
                }],
                "ttl_seconds_after_finished": 86400,
                "security_context": {
                    "allow_privilege_escalation": False,
                    "drop_capabilities": ["ALL"],
                },
            })
            self.assertTrue(s.is_valid(), s.errors)


def _compute():
    """A KubernetesCompute without __init__, which would load a kubeconfig."""
    compute = KubernetesCompute.__new__(KubernetesCompute)
    compute.namespace = "default"
    compute.batch_api = MagicMock()
    return compute


def _start(compute, **overrides):
    kwargs = dict(
        name="envbuild-6f1c2a9b",
        identifier="abc123",
        image="mismplatform/pi-envagent:k8s-test",
        command=None,
        env={"MODEL_ID": "mism:model/6f1c"},
        volumes=[
            {"pvc": "envbuild-work", "mount_path": "/work", "sub_path": "", "read_only": False},
            {"pvc": "irods-pvc", "mount_path": "/models", "sub_path": "", "read_only": True},
        ],
        limits={"cpus": "1", "memory": "2Gi"},
    )
    kwargs.update(overrides)
    result = compute.start_job(**kwargs)
    job = compute.batch_api.create_namespaced_job.call_args.kwargs["body"]
    return result, job


class TestStartJob(SimpleTestCase):
    def test_defaults_unchanged_for_existing_callers(self):
        """Model runs and annotation jobs pass none of the new args."""
        _, job = _start(_compute())
        pod = job.spec.template.spec
        container = pod.containers[0]
        self.assertIsNone(pod.service_account_name)
        self.assertIsNone(container.env_from)
        self.assertIsNone(container.security_context)
        self.assertIsNone(job.spec.ttl_seconds_after_finished)
        self.assertEqual([v.name for v in pod.volumes], ["envbuild-work", "irods-pvc"])

    def test_envbuild_job_shape(self):
        result, job = _start(
            _compute(),
            service_account="envbuild",
            env_from=[
                {"kind": "configmap", "name": "envbuild-tuning", "optional": True},
                {"kind": "secret", "name": "envbuild-llm", "optional": False},
            ],
            secret_mounts=[{
                "secret": "envbuild-registry-auth",
                "mount_path": "/home/node/.docker",
                "items": {".dockerconfigjson": "config.json"},
            }],
            ttl_seconds_after_finished=86400,
            security_context={"allow_privilege_escalation": False, "drop_capabilities": ["ALL"]},
        )
        self.assertEqual(result, {"name": "envbuild-6f1c2a9b-abc123", "sid": "abc123", "status": "running"})

        pod = job.spec.template.spec
        container = pod.containers[0]
        self.assertEqual(pod.service_account_name, "envbuild")
        self.assertEqual(job.spec.ttl_seconds_after_finished, 86400)
        self.assertEqual(job.spec.backoff_limit, 0)

        # envFrom keeps caller order: ConfigMap first, Secret last (Secret wins).
        self.assertEqual(container.env_from[0].config_map_ref.name, "envbuild-tuning")
        self.assertTrue(container.env_from[0].config_map_ref.optional)
        self.assertEqual(container.env_from[1].secret_ref.name, "envbuild-llm")

        secret_vol = next(v for v in pod.volumes if v.secret is not None)
        self.assertEqual(secret_vol.secret.secret_name, "envbuild-registry-auth")
        self.assertEqual(secret_vol.secret.items[0].key, ".dockerconfigjson")
        self.assertEqual(secret_vol.secret.items[0].path, "config.json")
        secret_mount = next(m for m in container.volume_mounts if m.name == secret_vol.name)
        self.assertEqual(secret_mount.mount_path, "/home/node/.docker")
        self.assertTrue(secret_mount.read_only)

        models_mount = next(m for m in container.volume_mounts if m.mount_path == "/models")
        self.assertTrue(models_mount.read_only)

        sc = container.security_context
        self.assertFalse(sc.allow_privilege_escalation)
        self.assertEqual(sc.capabilities.drop, ["ALL"])

        # MISM_GUID is still injected for correlation.
        self.assertIn("MISM_GUID", [e.name for e in container.env])

    def test_secret_mount_without_items_projects_all_keys(self):
        _, job = _start(_compute(), secret_mounts=[{"secret": "s", "mount_path": "/s"}])
        secret_vol = next(v for v in job.spec.template.spec.volumes if v.secret is not None)
        self.assertIsNone(secret_vol.secret.items)

    def test_security_context_without_drop_leaves_capabilities_unset(self):
        _, job = _start(_compute(), security_context={"allow_privilege_escalation": False})
        sc = job.spec.template.spec.containers[0].security_context
        self.assertFalse(sc.allow_privilege_escalation)
        self.assertIsNone(sc.capabilities)
