import importlib.resources

_KINDNET_MANIFEST = (
    importlib.resources.files(__package__)
    .joinpath("manifests/kindnet.yaml")
    .read_text(encoding="utf-8")
)

_PLACEHOLDER = "${DOCKER_POD_CIDRS},${DOCKER_POD_IPV6_CIDRS}"


def render_kindnet(pod_cidr: str) -> str:
    result = _KINDNET_MANIFEST.replace(_PLACEHOLDER, pod_cidr)
    if "${" in result:
        raise ValueError("render_kindnet: unreplaced placeholder in kindnet manifest")
    return result
