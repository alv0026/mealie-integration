import json
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from bridge.app import CreationStore, create_app

KEY = "test-bridge-key-" + "x" * 32
AUTH = {"Authorization": "Bearer " + KEY}
RECIPE = {"name": "Toast", "ingredients": ["1 slice bread"], "instructions": ["Toast the bread."]}


def app_for(tmp_path, handler):
    return create_app(mealie_url="https://mealie.test", mealie_token="private-upstream-token", api_key=KEY,
                      database=str(tmp_path / "state.sqlite3"), transport=httpx.MockTransport(handler))


def test_authentication_blocks_all_recipe_routes(tmp_path):
    def handler(request):
        pytest.fail("Unauthenticated request reached Mealie")
    with TestClient(app_for(tmp_path, handler)) as client:
        assert client.get("/health").status_code == 200
        for method, path, body in [("GET", "/recipes/search?q=toast", None), ("GET", "/recipes/toast", None),
                                   ("POST", "/recipes", RECIPE), ("PATCH", "/recipes/toast", {"name": "Toast"})]:
            for headers in [{}, {"Authorization": "Bearer wrong"}]:
                assert client.request(method, path, json=body, headers=headers).status_code == 401


def test_search_and_get_forward_only_upstream_token(tmp_path):
    def handler(request):
        assert request.headers["Authorization"] == "Bearer private-upstream-token"
        if request.url.path == "/api/recipes":
            assert dict(request.url.params) == {"search": "toast", "page": "2", "perPage": "5"}
            return httpx.Response(200, json={"items": [{"slug": "toast"}], "total": 1})
        assert request.url.path == "/api/recipes/toast"
        return httpx.Response(200, json={"slug": "toast", "name": "Toast"})
    with TestClient(app_for(tmp_path, handler)) as client:
        assert client.get("/recipes/search?q=toast&page=2&per_page=5", headers=AUTH).json()["total"] == 1
        assert client.get("/recipes/toast", headers=AUTH).json()["name"] == "Toast"


def test_create_and_durable_retry(tmp_path):
    calls = []
    def handler(request):
        calls.append(request.method)
        data = json.loads(request.content)
        if request.method == "POST":
            assert data == {"name": "Toast"}
            return httpx.Response(201, json="toast")
        assert data["recipeIngredient"][0]["note"] == "1 slice bread"
        assert data["recipeInstructions"] == [{"text": "Toast the bread."}]
        assert "settings" not in data and "userId" not in data
        return httpx.Response(200, json={"slug": "toast"})
    headers = AUTH | {"Idempotency-Key": "create-toast-001"}
    for _ in range(2):
        with TestClient(app_for(tmp_path, handler)) as client:
            response = client.post("/recipes", json=RECIPE, headers=headers)
            assert response.status_code == 201
            assert response.json() == {"slug": "toast", "status": "created"}
            assert client.post("/recipes", json=RECIPE | {"name": "Other"}, headers=headers).status_code == 409
    assert calls == ["POST", "PATCH"]


@pytest.mark.parametrize("failure_stage", ["POST", "PATCH"])
def test_uncertain_creation_is_not_repeated(tmp_path, failure_stage):
    calls = []
    def handler(request):
        calls.append(request.method)
        if request.method == failure_stage:
            raise httpx.ReadTimeout("sensitive error", request=request)
        return httpx.Response(201, json="toast")
    headers = AUTH | {"Idempotency-Key": "uncertain-toast"}
    with TestClient(app_for(tmp_path, handler)) as client:
        failed = client.post("/recipes", json=RECIPE, headers=headers)
        assert failed.status_code == 504
        assert failed.json()["detail"]["slug"] == ("toast" if failure_stage == "PATCH" else None)
        assert "sensitive" not in failed.text
        count = len(calls)
        assert client.post("/recipes", json=RECIPE, headers=headers).status_code == 409
        assert len(calls) == count


def test_patch_preserves_omitted_fields(tmp_path):
    def handler(request):
        assert request.method == "PATCH"
        assert json.loads(request.content) == {"description": "New description"}
        return httpx.Response(200, json={"name": "Toast", "description": "New description"})
    with TestClient(app_for(tmp_path, handler)) as client:
        assert client.patch("/recipes/toast", json={"description": "New description"}, headers=AUTH).status_code == 200


@pytest.mark.parametrize("body", [{}, {"name": " "}, {"ingredients": None}, {"settings": {"public": True}}, {"servings": -1}])
def test_invalid_updates_never_reach_mealie(tmp_path, body):
    def handler(request):
        pytest.fail("Invalid data reached Mealie")
    with TestClient(app_for(tmp_path, handler)) as client:
        assert client.patch("/recipes/toast", json=body, headers=AUTH).status_code == 422


@pytest.mark.parametrize("status,expected", [(401, 502), (403, 502), (404, 404), (409, 409), (422, 422), (429, 503), (500, 502), (302, 502)])
def test_upstream_errors_are_sanitized(tmp_path, status, expected):
    def handler(request):
        return httpx.Response(status, text="private-upstream-token", headers={"Location": "https://other.test"})
    with TestClient(app_for(tmp_path, handler)) as client:
        response = client.get("/recipes/toast", headers=AUTH)
        assert response.status_code == expected
        assert "private-upstream-token" not in response.text


def test_html_response_is_not_accepted(tmp_path):
    with TestClient(app_for(tmp_path, lambda r: httpx.Response(200, text="<html>Login</html>"))) as client:
        assert client.get("/recipes/toast", headers=AUTH).status_code == 502


def test_only_one_concurrent_reservation(tmp_path):
    store = CreationStore(str(tmp_path / "state.sqlite3"))
    def reserve(_):
        try:
            store.reserve("same-key", "same-digest")
            return True
        except HTTPException as exc:
            assert exc.status_code == 409
            return False
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(reserve, range(8))) == 1


def test_missing_config_fails_closed(tmp_path, monkeypatch):
    monkeypatch.delenv("BRIDGE_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        create_app(mealie_url="https://mealie.test", mealie_token="token", database=str(tmp_path / "db"))
