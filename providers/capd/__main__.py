import pulumi

from dataflow_capd import Cluster, ClusterArgs

cfg = pulumi.Config()

args = ClusterArgs(
    name=cfg.require("clusterName"),
    namespace=cfg.require("namespace"),
    kubernetes_version=cfg.require("kubernetesVersion"),
    pod_cidr=cfg.require("podCidr"),
    service_cidr=cfg.require("serviceCidr"),
    control_plane_replicas=cfg.require_int("controlPlaneReplicas"),
    worker_replicas=cfg.require_int("workerReplicas"),
)

cluster = Cluster(args.name, args)

pulumi.export("clusterName", cluster.cluster_name)
pulumi.export("namespace", cluster.namespace)
pulumi.export("kubeconfigSecretName", cluster.kubeconfig_secret_name)
pulumi.export("kubeconfigCommand", pulumi.Output.concat("kind get kubeconfig --name ", cluster.cluster_name))
