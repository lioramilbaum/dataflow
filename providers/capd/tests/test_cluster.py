from __future__ import annotations

import pytest
import pulumi

from dataflow_capd import Cluster, ClusterArgs
from tests.conftest import Recorder, find_one, find_resources, lookup, make_recorder


DEFAULT_ARGS = ClusterArgs(
    name="test-cluster",
    namespace="test-ns",
    kubernetes_version="v1.36.4",
    pod_cidr="192.168.0.0/16",
    service_cidr="10.128.0.0/12",
    control_plane_replicas=1,
    worker_replicas=2,
)

EXPECTED_TOKENS = {
    "capi:cluster.x-k8s.io/v1beta2:Cluster": 1,
    "capi:cluster.x-k8s.io/v1beta2:MachineDeployment": 1,
    "capi:controlplane.cluster.x-k8s.io/v1beta2:KubeadmControlPlane": 1,
    "capi:bootstrap.cluster.x-k8s.io/v1beta2:KubeadmConfigTemplate": 1,
    "capi:addons.cluster.x-k8s.io/v1beta2:ClusterResourceSet": 1,
    "capd:infrastructure.cluster.x-k8s.io/v1beta2:DockerCluster": 1,
    "capd:infrastructure.cluster.x-k8s.io/v1beta2:DockerMachineTemplate": 2,
    "kubernetes:core/v1:ConfigMap": 1,
    "kubernetes:core/v1:Namespace": 1,
}


def _run(args: ClusterArgs = DEFAULT_ARGS) -> tuple[Recorder, None]:
    rec = make_recorder()

    @pulumi.runtime.test
    def inner():
        c = Cluster(args.name, args)
        return c.cluster_name

    inner()
    return rec, None


@pytest.fixture
def recorder_and_resources():
    rec, _ = _run()
    return rec


def test_registers_typed_capi_resources(recorder_and_resources):
    rec = recorder_and_resources
    actual: dict[str, int] = {}
    for r in rec.resources:
        actual[r.typ] = actual.get(r.typ, 0) + 1

    for token, count in EXPECTED_TOKENS.items():
        assert actual.get(token, 0) == count, (
            f"expected {count} of {token}, got {actual.get(token, 0)}"
        )
    for token in actual:
        assert token in EXPECTED_TOKENS, f"unexpected resource type: {token}"


def test_refs_are_wired(recorder_and_resources):
    rec = recorder_and_resources
    dc = find_one(rec.resources, "capd:infrastructure.cluster.x-k8s.io/v1beta2:DockerCluster")
    kcp = find_one(rec.resources, "capi:controlplane.cluster.x-k8s.io/v1beta2:KubeadmControlPlane")
    cluster = find_one(rec.resources, "capi:cluster.x-k8s.io/v1beta2:Cluster")
    dmts = find_resources(rec.resources, "capd:infrastructure.cluster.x-k8s.io/v1beta2:DockerMachineTemplate")
    kct = find_one(rec.resources, "capi:bootstrap.cluster.x-k8s.io/v1beta2:KubeadmConfigTemplate")
    md = find_one(rec.resources, "capi:cluster.x-k8s.io/v1beta2:MachineDeployment")

    dc_name = lookup(dc.inputs, "metadata", "name")
    assert lookup(cluster.inputs, "spec", "infrastructureRef", "kind") == "DockerCluster"
    assert lookup(cluster.inputs, "spec", "infrastructureRef", "name") == dc_name

    kcp_name = lookup(kcp.inputs, "metadata", "name")
    assert lookup(cluster.inputs, "spec", "controlPlaneRef", "kind") == "KubeadmControlPlane"
    assert lookup(cluster.inputs, "spec", "controlPlaneRef", "name") == kcp_name

    cp_dmt = next(d for d in dmts if "control-plane" in d.name)
    cp_dmt_name = lookup(cp_dmt.inputs, "metadata", "name")
    assert lookup(kcp.inputs, "spec", "machineTemplate", "spec", "infrastructureRef", "name") == cp_dmt_name

    worker_dmt = next(d for d in dmts if "md-0" in d.name)
    worker_dmt_name = lookup(worker_dmt.inputs, "metadata", "name")
    assert lookup(md.inputs, "spec", "template", "spec", "infrastructureRef", "name") == worker_dmt_name

    kct_name = lookup(kct.inputs, "metadata", "name")
    assert lookup(md.inputs, "spec", "template", "spec", "bootstrap", "configRef", "name") == kct_name


def test_version_and_replicas(recorder_and_resources):
    rec = recorder_and_resources
    kcp = find_one(rec.resources, "capi:controlplane.cluster.x-k8s.io/v1beta2:KubeadmControlPlane")
    md = find_one(rec.resources, "capi:cluster.x-k8s.io/v1beta2:MachineDeployment")

    assert lookup(kcp.inputs, "spec", "version") == DEFAULT_ARGS.kubernetes_version
    assert lookup(md.inputs, "spec", "template", "spec", "version") == DEFAULT_ARGS.kubernetes_version
    assert lookup(kcp.inputs, "spec", "replicas") == DEFAULT_ARGS.control_plane_replicas
    assert lookup(md.inputs, "spec", "replicas") == DEFAULT_ARGS.worker_replicas


def test_waits_for_available(recorder_and_resources):
    rec = recorder_and_resources
    cluster = find_one(rec.resources, "capi:cluster.x-k8s.io/v1beta2:Cluster")
    annotations = lookup(cluster.inputs, "metadata", "annotations")
    assert annotations.get("pulumi.com/waitFor") == "condition=Available"
    assert annotations.get("pulumi.com/timeoutSeconds") == "1200"


def test_cni_via_cluster_resource_set(recorder_and_resources):
    rec = recorder_and_resources
    cm = find_one(rec.resources, "kubernetes:core/v1:ConfigMap")
    crs = find_one(rec.resources, "capi:addons.cluster.x-k8s.io/v1beta2:ClusterResourceSet")
    cluster = find_one(rec.resources, "capi:cluster.x-k8s.io/v1beta2:Cluster")

    kindnet_yaml = lookup(cm.inputs, "data", "kindnet.yaml")
    assert "192.168.0.0/16" in kindnet_yaml
    assert "${" not in kindnet_yaml

    cni_label = lookup(cluster.inputs, "metadata", "labels", "dataflow.io/cni")
    selector_label = lookup(crs.inputs, "spec", "clusterSelector", "matchLabels", "dataflow.io/cni")
    assert cni_label == selector_label

    cm_name = lookup(cm.inputs, "metadata", "name")
    assert lookup(crs.inputs, "spec", "resources", 0, "name") == cm_name


def test_kubeadm_settings(recorder_and_resources):
    rec = recorder_and_resources
    kcp = find_one(rec.resources, "capi:controlplane.cluster.x-k8s.io/v1beta2:KubeadmControlPlane")
    kct = find_one(rec.resources, "capi:bootstrap.cluster.x-k8s.io/v1beta2:KubeadmConfigTemplate")

    cert_sans = lookup(kcp.inputs, "spec", "kubeadmConfigSpec", "clusterConfiguration", "apiServer", "certSANs")
    assert cert_sans == ["localhost", "127.0.0.1", "0.0.0.0", "host.docker.internal"]

    for path in [
        ("spec", "kubeadmConfigSpec", "initConfiguration", "nodeRegistration", "kubeletExtraArgs"),
        ("spec", "kubeadmConfigSpec", "joinConfiguration", "nodeRegistration", "kubeletExtraArgs"),
    ]:
        args_list = lookup(kcp.inputs, *path)
        assert any(a.get("name") == "eviction-hard" for a in args_list)

    kct_args = lookup(kct.inputs, "spec", "template", "spec", "joinConfiguration", "nodeRegistration", "kubeletExtraArgs")
    assert any(a.get("name") == "eviction-hard" for a in kct_args)


def test_templates_are_auto_named(recorder_and_resources):
    rec = recorder_and_resources
    dmts = find_resources(rec.resources, "capd:infrastructure.cluster.x-k8s.io/v1beta2:DockerMachineTemplate")
    kct = find_one(rec.resources, "capi:bootstrap.cluster.x-k8s.io/v1beta2:KubeadmConfigTemplate")

    for r in dmts + [kct]:
        prog_meta = r.program_inputs.get("metadata") or {}
        assert "name" not in prog_meta, (
            f"{r.typ} ({r.name}) should be auto-named but program supplied metadata.name={prog_meta.get('name')!r}"
        )


def test_docker_machine_template_has_template_spec(recorder_and_resources):
    rec = recorder_and_resources
    for dmt in find_resources(rec.resources, "capd:infrastructure.cluster.x-k8s.io/v1beta2:DockerMachineTemplate"):
        spec = lookup(dmt.inputs, "spec")
        assert "template" in spec, f"DockerMachineTemplate {dmt.name} missing spec.template"
        assert "spec" in spec["template"], f"DockerMachineTemplate {dmt.name} missing spec.template.spec"


def test_children_use_namespace_output(recorder_and_resources):
    rec = recorder_and_resources
    for r in rec.resources:
        if r.typ in ("kubernetes:core/v1:Namespace",):
            continue
        meta = r.inputs.get("metadata")
        if meta is None:
            continue
        ns = meta.get("namespace")
        if ns is not None:
            # Note: this test verifies the resolved namespace string is correct.
            # It cannot verify that metadata.namespace was wired to the Namespace's
            # name Output (which creates implicit ordering). That is verified by
            # code inspection of cluster.py (_namespaced uses ns_name, an Output[str]).
            assert ns == DEFAULT_ARGS.namespace, f"{r.typ} has wrong namespace: {ns}"


@pytest.mark.parametrize("bad_args,match", [
    ({"name": ""}, "name"),
    ({"kubernetes_version": "1.36.4"}, "kubernetes_version"),
    ({"control_plane_replicas": 2}, "control_plane_replicas"),
    ({"control_plane_replicas": 0}, "control_plane_replicas"),
    ({"worker_replicas": -1}, "worker_replicas"),
    ({"pod_cidr": "bad-cidr"}, "pod_cidr"),
    ({"pod_cidr": "10.128.0.0"}, "pod_cidr"),  # missing prefix
    ({"service_cidr": "bad-cidr"}, "service_cidr"),
])
def test_cluster_args_validation(bad_args, match):
    import dataclasses
    with pytest.raises(ValueError, match=match):
        dataclasses.replace(DEFAULT_ARGS, **bad_args)
