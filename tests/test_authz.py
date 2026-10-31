from fastapi.testclient import TestClient


def _client(monkeypatch, readonly: bool):
    monkeypatch.setenv("GEAP_PUBLIC_READONLY", "1" if readonly else "0")
    monkeypatch.setenv("GEAP_IAP_AUDIENCE", "/projects/1/global/backendServices/2")
    monkeypatch.setenv("GEAP_ADMIN_EMAILS", "admin@example.com")
    from geap_eval.server import create_app
    return TestClient(create_app())


CFG = {"run": {"name": "authz-test"}, "harnesses": ["pi"], "tasks": ["banking/iban-checksum-bug"],
       "model_profiles": [{"id": "f", "roles": {"default": {"model": "gemini-3.8-flash", "thinking": "low"}}}]}


def test_public_readonly_blocks_writes(monkeypatch):
    c = _client(monkeypatch, readonly=True)
    assert c.get("/api/me").json() == {"admin": False, "email": None, "readonly": True}
    assert c.post("/api/runs", json=CFG).status_code == 403
    assert c.post("/api/runs?_admin_checked=true", json=CFG).status_code == 403          # no bypass via query param
    assert c.post("/api/admin/runs", json=CFG).status_code == 403                        # no IAP JWT
    assert c.post("/api/admin/runs", json=CFG, headers={"x-goog-iap-jwt-assertion": "forged.jwt.value"}).status_code == 403
    assert c.post("/api/runs/x/cancel").status_code == 403
    assert c.post("/api/admin/runs/x/cancel").status_code == 403
    assert c.post("/api/runs?dry_run=1", json=CFG).status_code == 200                    # read-only preview allowed
    assert c.get("/api/health").status_code == 200


def test_local_mode_allows_admin(monkeypatch):
    c = _client(monkeypatch, readonly=False)
    assert c.get("/api/me").json()["admin"] is True
