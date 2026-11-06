"""HTTP API and web UI.  Run:  uvicorn allergencheck.api:app"""
import logging
import time
import uuid
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from . import barcode
from .engine import Profile, analyze
from .rules import CATEGORIES

MAX_IMAGE_BYTES = 6 * 1024 * 1024
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic"}
STATIC = Path(__file__).parent / "static"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("allergencheck")

app = FastAPI(title="AllergenCheck", version="2.0.0")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class ProfileIn(BaseModel):
    avoid: list[str] = Field(default_factory=list, max_length=len(CATEGORIES))
    custom: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("avoid")
    @classmethod
    def known(cls, v):
        bad = [k for k in v if k not in CATEGORIES]
        if bad:
            raise ValueError(f"unknown categories: {bad}")
        return v

    @field_validator("custom")
    @classmethod
    def clean(cls, v):
        return [w.strip()[:40] for w in v if w.strip()]

    def to_profile(self) -> Profile:
        return Profile(self.avoid, self.custom)


class TextIn(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)
    profile: ProfileIn


class AnalysisOut(BaseModel):
    source: Literal["photo", "text", "barcode"]
    report: dict
    ocr_confidence: float | None = None
    product: dict | None = None
    ms: float


@app.middleware("http")
async def request_log(request: Request, call_next):
    rid = uuid.uuid4().hex[:8]
    t0 = time.perf_counter()
    response = await call_next(request)
    log.info("rid=%s %s %s -> %s in %.0fms", rid, request.method, request.url.path, response.status_code,
             (time.perf_counter() - t0) * 1000)
    response.headers["X-Request-ID"] = rid
    return response


@app.exception_handler(ValueError)
async def value_error(_, exc: ValueError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
async def health():
    return {"ok": True}


@app.get("/api/categories")
async def categories():
    return [{"key": c.key, "label": c.label, "kind": c.kind} for c in CATEGORIES.values()]


@app.post("/api/analyze/text", response_model=AnalysisOut)
async def analyze_text(body: TextIn):
    t0 = time.perf_counter()
    report = analyze(body.text, body.profile.to_profile())
    return AnalysisOut(source="text", report=report.to_dict(), ms=_ms(t0))


@app.post("/api/analyze/photo", response_model=AnalysisOut)
async def analyze_photo(image: UploadFile = File(...), profile: str = Form(...)):
    t0 = time.perf_counter()
    prof = ProfileIn.model_validate_json(profile).to_profile()
    if image.content_type not in IMAGE_TYPES:
        raise HTTPException(415, "Upload a JPEG, PNG or WebP photo.")
    data = await image.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Photo is larger than 6 MB.")
    from .ocr import read_label  # heavy imports only when photos are used

    ocr = read_label(data)  # in memory: nothing is written to disk
    report = analyze(ocr.text, prof)
    return AnalysisOut(source="photo", report=report.to_dict(), ocr_confidence=ocr.confidence, ms=_ms(t0))


@app.get("/api/analyze/barcode/{code}", response_model=AnalysisOut)
async def analyze_barcode(code: str, avoid: str = "", custom: str = ""):
    t0 = time.perf_counter()
    prof = ProfileIn(avoid=[a for a in avoid.split(",") if a], custom=[c for c in custom.split(",") if c])
    try:
        product = await barcode.lookup(code)
    except barcode.ProductNotFound:
        raise HTTPException(404, "That barcode isn't in Open Food Facts yet. Try a photo of the label instead.")
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    if not product.ingredients_text:
        raise HTTPException(404, "Found the product, but it has no ingredient list. Try a photo of the label.")
    report = analyze(product.ingredients_text, prof.to_profile())
    return AnalysisOut(source="barcode", report=report.to_dict(), ms=_ms(t0),
                       product={"name": product.name, "brand": product.brand, "image_url": product.image_url})


def _ms(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000, 1)
