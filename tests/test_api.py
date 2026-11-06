import json

import pytest

httpx = pytest.importorskip("httpx")

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from allergencheck import api, barcode  # noqa: E402

client = TestClient(api.app)
PROFILE = {"avoid": ["peanut", "milk"], "custom": []}


def test_health_and_ui():
    assert client.get("/api/health").json() == {"ok": True}
    assert "AllergenCheck" in client.get("/").text


def test_categories_lists_major_allergens():
    keys = {c["key"] for c in client.get("/api/categories").json()}
    assert {"peanut", "milk", "sesame", "gluten"} <= keys


def test_text_analysis():
    r = client.post("/api/analyze/text", json={"text": "Ingredients: sugar, peanuts.", "profile": PROFILE})
    assert r.status_code == 200
    body = r.json()
    assert body["report"]["verdict"] == "unsafe" and body["source"] == "text"
    assert "X-Request-ID" in r.headers


def test_unknown_category_is_422():
    r = client.post("/api/analyze/text", json={"text": "x", "profile": {"avoid": ["kryptonite"]}})
    assert r.status_code == 422


def test_photo_rejects_non_images():
    r = client.post("/api/analyze/photo", files={"image": ("a.txt", b"hello", "text/plain")},
                    data={"profile": json.dumps(PROFILE)})
    assert r.status_code == 415


def test_barcode_uses_open_food_facts(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert "3017620422003" in str(request.url)
        return httpx.Response(200, json={"status": 1, "product": {
            "product_name": "Hazelnut spread", "brands": "Example",
            "ingredients_text_en": "Sugar, palm oil, hazelnuts 13%, skimmed milk powder 8.7%, cocoa.",
            "allergens_tags": ["en:milk", "en:nuts"], "traces_tags": []}})

    real = barcode.lookup

    async def fake_lookup(code, client=None):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await real(code, c)

    monkeypatch.setattr(barcode, "lookup", fake_lookup)
    r = client.get("/api/analyze/barcode/3017620422003", params={"avoid": "milk,tree_nut"})
    assert r.status_code == 200
    body = r.json()
    assert body["product"]["name"] == "Hazelnut spread"
    assert body["report"]["verdict"] == "unsafe"
    assert {f["category"] for f in body["report"]["findings"]} == {"milk", "tree_nut"}


def test_bad_barcode_is_422():
    assert client.get("/api/analyze/barcode/12ab").status_code == 422
