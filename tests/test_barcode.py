import asyncio

import pytest

httpx = pytest.importorskip("httpx")

from allergencheck import barcode


def run(handler, code="0123456789012"):
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await barcode.lookup(code, c)
    return asyncio.run(go())


def test_tags_become_statements():
    p = run(lambda r: httpx.Response(200, json={"status": 1, "product": {
        "product_name": "Bar", "ingredients_text": "Oats, honey", "allergens_tags": ["en:milk"],
        "traces_tags": ["en:peanuts"]}}))
    assert "Contains: milk." in p.ingredients_text and "May contain peanuts." in p.ingredients_text


def test_not_found():
    with pytest.raises(barcode.ProductNotFound):
        run(lambda r: httpx.Response(200, json={"status": 0}))


def test_invalid_code():
    with pytest.raises(ValueError):
        run(lambda r: httpx.Response(200), code="abc")
