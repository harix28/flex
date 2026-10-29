import pytest

@pytest.fixture(autouse=True)
def isolated_release_pointer(tmp_path, monkeypatch):
    from sentinel.mlops import deployment
    monkeypatch.setattr(deployment, 'RELEASE_POINTER_FILE', tmp_path / 'active_release.json')
