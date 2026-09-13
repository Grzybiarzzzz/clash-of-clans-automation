"""Static frontend routes must never serve files outside the frontend build."""
import importlib
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def static_client(tmp_path, monkeypatch):
    import web.server as server
    build = Path(server.__file__).parent / 'frontend' / 'dist'
    created = not build.exists()
    if created:
        (build / 'assets').mkdir(parents=True)
    try:
        server = importlib.reload(server)
        frontend = tmp_path / 'frontend'
        frontend.mkdir()
        (frontend / 'index.html').write_text('FRONTEND')
        (tmp_path / 'private_config.py').write_text('PRIVATE SENTINEL')
        (frontend / 'linked.py').symlink_to(tmp_path / 'private_config.py')
        monkeypatch.setattr(server, 'FRONTEND_DIR', frontend)
        yield TestClient(server.app)
    finally:
        if created:
            shutil.rmtree(build)
        importlib.reload(server)


def test_frontend_navigation(static_client):
    response = static_client.get('/settings')
    assert response.status_code == 200
    assert response.text == 'FRONTEND'


def test_parent_path_is_rejected(static_client):
    response = static_client.get('/%2e%2e/private_config.py')
    assert response.status_code == 404
    assert 'PRIVATE SENTINEL' not in response.text


def test_external_symlink_is_rejected(static_client):
    response = static_client.get('/linked.py')
    assert response.status_code == 404
    assert 'PRIVATE SENTINEL' not in response.text
