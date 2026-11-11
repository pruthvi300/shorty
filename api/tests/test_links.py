import pytest


def test_create_link_returns_short_url(make_link):
    link = make_link(title="Docs")
    assert link["short_url"] == f"https://sho.rt/{link['short_code']}"
    assert len(link["short_code"]) == 8
    assert link["title"] == "Docs"
    assert link["click_count"] == 0


def test_create_link_adds_https_when_scheme_missing(make_link):
    assert make_link(url="example.com/x")["original_url"] == "https://example.com/x"


@pytest.mark.parametrize(
    "bad_url",
    ["", "javascript:alert(1)", "ftp://example.com/file", "not a url", "https://", "http://exa mple.com", None, 42],
)
def test_create_link_rejects_bad_urls(client, bad_url):
    response = client.post("/api/links", json={"url": bad_url})
    assert response.status_code == 400


def test_create_link_requires_json_object(client):
    assert client.post("/api/links", data="nope", content_type="text/plain").status_code == 400
    assert client.post("/api/links", json=["https://example.com"]).status_code == 400


def test_custom_code(make_link, client):
    assert make_link(custom_code="my-link")["short_code"] == "my-link"
    duplicate = client.post("/api/links", json={"url": "https://example.com", "custom_code": "my-link"})
    assert duplicate.status_code == 409


@pytest.mark.parametrize("code", ["ab", "has space", "slash/es", "health", "API", "x" * 33])
def test_custom_code_validation(client, code):
    response = client.post("/api/links", json={"url": "https://example.com", "custom_code": code})
    assert response.status_code == 400


def test_generated_code_collision_is_retried(client, make_link, monkeypatch):
    make_link(custom_code="taken01")
    codes = iter(["taken01", "fresh01"])
    monkeypatch.setattr("app.routes.links.generate_short_code", lambda: next(codes))
    assert make_link()["short_code"] == "fresh01"


def test_list_links_paginates_and_hides_deleted(client, make_link):
    first = make_link()
    make_link()
    client.delete(f"/api/links/{first['id']}")
    body = client.get("/api/links?per_page=1").get_json()
    assert body["total"] == 1
    assert len(body["links"]) == 1


def test_update_link_validates_input(client, make_link):
    link = make_link()
    assert client.patch(f"/api/links/{link['id']}", json={"is_active": "no"}).status_code == 400
    response = client.patch(f"/api/links/{link['id']}", json={"title": "Renamed"})
    assert response.status_code == 200
    assert response.get_json()["title"] == "Renamed"


def test_unknown_link_is_json_404(client):
    response = client.get("/api/links/999")
    assert response.status_code == 404
    assert "error" in response.get_json()
