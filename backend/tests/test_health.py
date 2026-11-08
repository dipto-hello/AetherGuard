import re
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, headers={"Authorization": "Bearer test-only-operator-token"})

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "aetherguard-governance-engine"


def test_security_headers_cover_frontend_and_unauthorized_api():
    for response in (client.get('/'), TestClient(app).get('/api/sandbox/orders')):
        assert response.headers['x-content-type-options'] == 'nosniff'
        assert response.headers['x-frame-options'] == 'DENY'
        assert "frame-ancestors 'none'" in response.headers['content-security-policy']
    assert TestClient(app).get('/api/sandbox/orders').headers['cache-control'] == 'no-store'


def test_api_does_not_allow_cross_origin_browser_access():
    response = client.get('/api/sandbox/orders', headers={'Origin': 'http://localhost:5173'})
    assert 'access-control-allow-origin' not in response.headers

def test_frontend_index_served():
    response = client.get("/")
    assert response.status_code == 200
    assert "<!doctype html>" in response.text.lower()
    assert "aetherguard" in response.text.lower() or "viewport" in response.text.lower()

def test_frontend_assets_served():
    response = client.get("/")
    assets = re.findall(r'href="(/assets/[^"]+)"', response.text) + re.findall(r'src="(/assets/[^"]+)"', response.text)
    assert len(assets) > 0, "No assets found in index.html"
    for asset_path in assets:
        asset_res = client.get(asset_path)
        assert asset_res.status_code == 200
        assert len(asset_res.content) > 0
