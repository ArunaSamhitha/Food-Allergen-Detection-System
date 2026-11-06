"""Look up a product's ingredient list by barcode in Open Food Facts (free, no key)."""
import re
from dataclasses import dataclass

import httpx

API = "https://world.openfoodfacts.org/api/v2/product/{code}.json"
FIELDS = "product_name,brands,ingredients_text_en,ingredients_text,allergens_tags,traces_tags,image_front_small_url"
USER_AGENT = "AllergenCheck/1.0 (github.com/ArunaSamhitha/Food-Allergen-Detection-System)"


@dataclass
class Product:
    barcode: str
    name: str
    brand: str
    ingredients_text: str
    allergen_tags: list[str]
    trace_tags: list[str]
    image_url: str | None


class ProductNotFound(Exception):
    pass


def valid_barcode(code: str) -> bool:
    return bool(re.fullmatch(r"\d{8,14}", code))


async def lookup(code: str, client: httpx.AsyncClient | None = None) -> Product:
    if not valid_barcode(code):
        raise ValueError("A barcode is 8 to 14 digits.")
    own = client is None
    client = client or httpx.AsyncClient(timeout=8, headers={"User-Agent": USER_AGENT})
    try:
        resp = await client.get(API.format(code=code), params={"fields": FIELDS})
        if resp.status_code == 404:
            raise ProductNotFound(code)
        resp.raise_for_status()
        body = resp.json()
    finally:
        if own:
            await client.aclose()
    if body.get("status") != 1 or "product" not in body:
        raise ProductNotFound(code)
    p = body["product"]
    text = p.get("ingredients_text_en") or p.get("ingredients_text") or ""
    # Database tags (e.g. "en:milk") become a Contains/May contain statement the engine can read.
    tags = [t.split(":", 1)[-1].replace("-", " ") for t in p.get("allergens_tags", [])]
    traces = [t.split(":", 1)[-1].replace("-", " ") for t in p.get("traces_tags", [])]
    if tags:
        text += f". Contains: {', '.join(tags)}."
    if traces:
        text += f" May contain {', '.join(traces)}."
    return Product(code, p.get("product_name", ""), p.get("brands", ""), text.strip(), tags, traces,
                   p.get("image_front_small_url"))
