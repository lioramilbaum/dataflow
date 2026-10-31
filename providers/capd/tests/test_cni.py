from dataflow_capd.cni import render_kindnet, _KINDNET_MANIFEST


def test_render_kindnet_substitutes_cidr():
    result = render_kindnet("192.168.0.0/16")
    assert "192.168.0.0/16" in result
    assert "${" not in result


def test_render_kindnet_raises_on_unknown_placeholder():
    import pytest
    # Temporarily break the placeholder detection by using a fresh string
    from dataflow_capd import cni as cni_mod
    original = cni_mod._PLACEHOLDER
    cni_mod._PLACEHOLDER = "__WRONG_PLACEHOLDER__"
    try:
        with pytest.raises(ValueError, match="unreplaced placeholder"):
            render_kindnet("192.168.0.0/16")
    finally:
        cni_mod._PLACEHOLDER = original


def test_kindnet_manifest_loads():
    assert len(_KINDNET_MANIFEST) > 0
    assert "kind: DaemonSet" in _KINDNET_MANIFEST
