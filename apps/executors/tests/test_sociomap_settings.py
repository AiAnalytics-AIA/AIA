"""Workspace switch parsing never depends on the AI runtime switch."""

import pytest
from aia_executors.sociomap_settings import SociomapSettings


def test_explicit_enable_disable_and_invalid_values(monkeypatch: pytest.MonkeyPatch) -> None:
    assert not SociomapSettings.from_env({}).workspace_enabled
    assert SociomapSettings.from_env({"AIA_SOCIOMAP_WORKSPACE_ENABLED": "true"}).workspace_enabled
    assert not SociomapSettings.from_env({"AIA_SOCIOMAP_WORKSPACE_ENABLED": "0"}).workspace_enabled
    with pytest.raises(ValueError, match="must be"):
        SociomapSettings.from_env({"AIA_SOCIOMAP_WORKSPACE_ENABLED": "yes please"})
    monkeypatch.setenv("AIA_SOCIOMAP_WORKSPACE_ENABLED", "1")
    assert SociomapSettings.from_env().workspace_enabled
