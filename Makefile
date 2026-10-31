CAPI_VERSION  := v1.14.3
PULUMI_K8S_VERSION := 4.34.2
MGMT          := capi-mgmt
PROJECT       := providers/capd
CRD_DIR       := $(PROJECT)/crds/cluster-api-$(CAPI_VERSION)
BASE_URL      := https://github.com/kubernetes-sigs/cluster-api/releases/download/$(CAPI_VERSION)

.PHONY: crds mgmt-up mgmt-down sdk-init sdk test preview up destroy kubeconfig

crds:
	mkdir -p $(CRD_DIR)
	curl -fsSL $(BASE_URL)/core-components.yaml -o $(CRD_DIR)/core-components.yaml
	curl -fsSL $(BASE_URL)/bootstrap-components.yaml -o $(CRD_DIR)/bootstrap-components.yaml
	curl -fsSL $(BASE_URL)/control-plane-components.yaml -o $(CRD_DIR)/control-plane-components.yaml
	curl -fsSL $(BASE_URL)/infrastructure-components-development.yaml -o $(CRD_DIR)/infrastructure-components-development.yaml

mgmt-up:
	kind create cluster --config infra/management/kind-config.yaml
	clusterctl init \
	  --core cluster-api:$(CAPI_VERSION) \
	  --bootstrap kubeadm:$(CAPI_VERSION) \
	  --control-plane kubeadm:$(CAPI_VERSION) \
	  --infrastructure docker:$(CAPI_VERSION) \
	  --wait-providers

mgmt-down:
	kind delete cluster --name $(MGMT)

sdk-init:
	cd $(PROJECT) && pulumi package add kubernetes@$(PULUMI_K8S_VERSION) \
	  --extension "name=capi version=$(CAPI_VERSION:v%=%) \
	  crd-manifest=crds/cluster-api-$(CAPI_VERSION)/core-components.yaml \
	  crd-manifest=crds/cluster-api-$(CAPI_VERSION)/bootstrap-components.yaml \
	  crd-manifest=crds/cluster-api-$(CAPI_VERSION)/control-plane-components.yaml"
	cd $(PROJECT) && pulumi package add kubernetes@$(PULUMI_K8S_VERSION) \
	  --extension "name=capd version=$(CAPI_VERSION:v%=%) \
	  crd-manifest=crds/cluster-api-$(CAPI_VERSION)/infrastructure-components-development.yaml"

sdk:
	cd $(PROJECT) && pulumi install

test:
	cd $(PROJECT) && uv run pyright && uv run pytest

preview:
	pulumi -C $(PROJECT) -s dev preview

up:
	pulumi -C $(PROJECT) -s dev up

destroy:
	pulumi -C $(PROJECT) -s dev destroy

kubeconfig:
	kind get kubeconfig --name dataflow-dev > dataflow-dev.kubeconfig
