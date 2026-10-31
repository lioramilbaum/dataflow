# dataflow

Large-scale data processing on Kubernetes using Spark, Volcano, and Cluster API.

## Step 1: Local cluster with CAPD

Provisions a Kubernetes workload cluster locally via [Cluster API Provider Docker (CAPD)](https://cluster-api.sigs.k8s.io/user/quick-start).
Infrastructure is defined as typed Python code using [Pulumi Kubernetes Provider Extensions](https://www.pulumi.com/blog/kubernetes-crds-as-provider-extensions/) — no bash scripts.

### Prerequisites

- Docker Desktop (≥ 6 GB memory, default Docker socket at `/var/run/docker.sock`)
- [kind](https://kind.sigs.k8s.io/) ≥ 0.33
- [clusterctl](https://cluster-api.sigs.k8s.io/user/quick-start#install-clusterctl) v1.14.x
- [Pulumi CLI](https://www.pulumi.com/docs/install/) ≥ 3.255.0
- uv ≥ 0.5 (Python 3.14 fetched automatically by uv)

### Quickstart

```sh
# 1. Download CAPI CRD manifests (only needed when bumping CAPI_VERSION)
make crds

# 2. Create the CAPI management cluster
make mgmt-up

# 3. Generate typed provider extension SDKs from CRDs
make sdk-init   # run once; populates Pulumi.yaml packages: block
make sdk        # run after every CAPI version bump

# 4. Init Pulumi stack (local backend)
pulumi login --local   # state stored in ~/.pulumi
pulumi -C providers/capd stack init dev

# 5. Deploy the workload cluster
make test
make up

# 6. Get the kubeconfig (macOS: kind rewrites the server address)
make kubeconfig
kubectl --kubeconfig dataflow-dev.kubeconfig get nodes

# 7. Tear down
make destroy
make mgmt-down
```

### Layout

```text
infra/management/     # kind config for the CAPI management cluster
providers/capd/       # Pulumi project: provider extension + cluster stack
  crds/               # vendored CAPI CRD manifests (inputs to pulumi package add)
  sdks/               # generated Python SDKs pulumi_capi/pulumi_capd (gitignored)
  dataflow_capd/      # Cluster component + CNI helpers
  __main__.py         # Pulumi entrypoint
  tests/              # pytest + mock-based unit tests
```

### Bumping the CAPI version

1. Update `CAPI_VERSION` in `Makefile`
2. `make crds` to download new CRD manifests
3. `make sdk-init` to regenerate the provider extensions
4. `make crds sdk-init sdk test` to rebuild and verify
