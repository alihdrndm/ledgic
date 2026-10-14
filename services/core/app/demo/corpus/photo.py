"""Dock-photo simulation: PDF page -> raster (pypdfium2) -> smudge/signature on paper -> perspective
and rotation onto a dock surface -> lighting gradient, blur, noise, JPEG artifacts.

Geometry is a pure function of the seed (``photo_params``) so the planner can map field bboxes to
photo coordinates without rendering anything (``map_bbox``).
"""

from __future__ import annotations

import io
import math
import random
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .layout import PAGE_H, PAGE_W

PHOTO_W, PHOTO_H = 1200, 1600
RASTER_SCALE = 2.0  # px per PDF point for the page raster
RASTER_W, RASTER_H = round(PAGE_W * RASTER_SCALE), round(PAGE_H * RASTER_SCALE)


@dataclass(frozen=True)
class PhotoParams:
    seed: int
    skew_deg: float  # in-plane rotation of the page, + = counter-clockwise as seen in the photo
    persp_deg: float  # keystone tilt, + = top edge farther from the camera
    cx: float
    cy: float
    page_h: float  # page height in photo pixels (before perspective)
    bg_tone: tuple[int, int, int]
    light_angle: float
    light_strength: float
    blur: float
    motion: bool
    fold: bool
    coffee_ring: bool
    jpeg_quality: int


def photo_params(seed: int, skew_deg: float | None = None) -> PhotoParams:
    r = random.Random(seed)
    drawn = round(r.choice([-1, 1]) * r.uniform(0.6, 4.0), 1)  # always drawn: keeps the stream stable
    if skew_deg is None:
        skew_deg = drawn
    persp = round(r.uniform(-8.0, 8.0), 1)
    tone_base = r.randint(88, 128)
    return PhotoParams(
        seed=seed,
        skew_deg=float(skew_deg),
        persp_deg=persp,
        cx=PHOTO_W / 2 + r.uniform(-18, 18),
        cy=PHOTO_H / 2 + r.uniform(-20, 20),
        page_h=PHOTO_H * r.uniform(0.78, 0.84),
        bg_tone=(tone_base + r.randint(0, 12), tone_base + r.randint(-4, 6), tone_base - r.randint(0, 14)),
        light_angle=r.uniform(0, 2 * math.pi),
        light_strength=r.uniform(0.18, 0.32),
        blur=r.uniform(0.3, 0.6),
        motion=r.random() < 0.2,
        fold=r.random() < 0.35,
        coffee_ring=r.random() < 0.15,
        jpeg_quality=r.randint(72, 82),
    )


def page_quad(p: PhotoParams) -> np.ndarray:
    """Photo-pixel corners of the page: TL, TR, BR, BL."""
    h = p.page_h
    w = h * PAGE_W / PAGE_H
    k = math.tan(math.radians(abs(p.persp_deg))) * 0.55  # keystone shrink of the far edge
    top_w, bot_w = (w * (1 - k), w) if p.persp_deg >= 0 else (w, w * (1 - k))
    h_eff = h * (1 - k * 0.35)
    pts = np.array(
        [[-top_w / 2, -h_eff / 2], [top_w / 2, -h_eff / 2], [bot_w / 2, h_eff / 2], [-bot_w / 2, h_eff / 2]]
    )
    th = math.radians(p.skew_deg)
    rot = np.array([[math.cos(th), math.sin(th)], [-math.sin(th), math.cos(th)]])
    return pts @ rot.T + np.array([p.cx, p.cy])


def _homography(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    a, b = [], []
    for (x, y), (u, v) in zip(src, dst, strict=True):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        b.append(u)
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        b.append(v)
    h = np.linalg.solve(np.array(a, dtype=float), np.array(b, dtype=float))
    return np.append(h, 1.0).reshape(3, 3)


def _raster_corners() -> np.ndarray:
    return np.array([[0, 0], [RASTER_W, 0], [RASTER_W, RASTER_H], [0, RASTER_H]], dtype=float)


def forward_h(p: PhotoParams) -> np.ndarray:
    return _homography(_raster_corners(), page_quad(p))


def map_bbox(bbox: dict, p: PhotoParams) -> dict:
    """Map a normalized page bbox to a normalized photo bbox (axis-aligned hull of the warped box)."""
    h = forward_h(p)
    x0, y0 = bbox["x"] * RASTER_W, bbox["y"] * RASTER_H
    x1, y1 = (bbox["x"] + bbox["w"]) * RASTER_W, (bbox["y"] + bbox["h"]) * RASTER_H
    pts = np.array([[x0, y0, 1], [x1, y0, 1], [x1, y1, 1], [x0, y1, 1]], dtype=float) @ h.T
    pts = pts[:, :2] / pts[:, 2:3]
    nx0, ny0 = max(0.0, float(pts[:, 0].min()) / PHOTO_W), max(0.0, float(pts[:, 1].min()) / PHOTO_H)
    nx1, ny1 = min(1.0, float(pts[:, 0].max()) / PHOTO_W), min(1.0, float(pts[:, 1].max()) / PHOTO_H)
    return {
        "page": 1,
        "x": round(nx0, 4),
        "y": round(ny0, 4),
        "w": round(nx1 - nx0, 4),
        "h": round(ny1 - ny0, 4),
    }


def rasterize_pdf_page(pdf_bytes: bytes, page_index: int = 0) -> Image.Image:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(pdf_bytes)
    try:
        page = pdf[page_index]
        img = page.render(scale=RASTER_SCALE).to_pil().convert("RGB")
        page.close()
    finally:
        pdf.close()
    if img.size != (RASTER_W, RASTER_H):
        img = img.resize((RASTER_W, RASTER_H), Image.Resampling.BICUBIC)
    return img


def _smudge(img: Image.Image, bbox: dict, r: random.Random) -> Image.Image:
    """Controlled smudge: blur + greasy thumb-print blob over the field; the digit stays faintly visible."""
    x0, y0 = bbox["x"] * RASTER_W, bbox["y"] * RASTER_H
    w, h = bbox["w"] * RASTER_W, bbox["h"] * RASTER_H
    cx, cy = x0 + w / 2 + r.uniform(-2, 2), y0 + h / 2 + r.uniform(-1, 1)
    pad = int(max(w, h) * 1.4) + 8
    box = (int(cx - pad), int(cy - pad), int(cx + pad), int(cy + pad))
    region = img.crop(box).filter(ImageFilter.GaussianBlur(2.2))
    img.paste(region, box[:2])
    arr = np.asarray(img).astype(np.float32)
    yy, xx = np.mgrid[0:RASTER_H, 0:RASTER_W]
    rx, ry = max(w * 0.9, 18.0), max(h * 0.85, 14.0)
    ang = r.uniform(-0.6, 0.6)
    dx, dy = xx - cx, yy - cy
    u = (dx * math.cos(ang) + dy * math.sin(ang)) / rx
    v = (-dx * math.sin(ang) + dy * math.cos(ang)) / ry
    blob = np.exp(-(u**2 + v**2) * 1.4)
    # streaky texture so it reads as a smear, not a rectangle
    streak = 0.75 + 0.25 * np.sin(u * 9 + v * 3 + r.uniform(0, 6))
    alpha = (blob * streak * r.uniform(0.50, 0.60))[..., None]
    color = np.array([108, 100, 92], dtype=np.float32)
    arr = arr * (1 - alpha) + color * alpha
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8))


def _signature(img: Image.Image, anchor: tuple[int, float, float, float], r: random.Random) -> None:
    _, x, y, width = anchor
    d = ImageDraw.Draw(img)
    x0, y0 = x * RASTER_SCALE, (y + 6) * RASTER_SCALE
    span = width * RASTER_SCALE * r.uniform(0.7, 0.95)
    pts = []
    f1, f2, ph = r.uniform(0.035, 0.06), r.uniform(0.09, 0.15), r.uniform(0, 6)
    for i in range(140):
        t = i / 139
        xx = x0 + t * span
        yy = y0 + 10 * math.sin(xx * f1 / 1.4 + ph) + 5 * math.sin(xx * f2 / 1.4) - 14 * t * (1 - t)
        pts.append((xx, yy))
    d.line(pts, fill=(28, 36, 92), width=3, joint="curve")


def _background(p: PhotoParams, r: np.random.Generator) -> np.ndarray:
    low = r.normal(0, 1, (12, 9)).astype(np.float32)
    low_img = Image.fromarray(((low - low.min()) / (np.ptp(low) + 1e-6) * 255).astype(np.uint8))
    tex = (
        np.asarray(low_img.resize((PHOTO_W, PHOTO_H), Image.Resampling.BICUBIC)).astype(np.float32) / 255
        - 0.5
    )
    base = np.array(p.bg_tone, dtype=np.float32)
    bg = base[None, None, :] * (1 + tex[..., None] * 0.28)
    # a couple of plank/expansion-joint lines for a dock floor
    for _ in range(2):
        y = int(r.uniform(0.05, 0.95) * PHOTO_H)
        bg[max(0, y - 2) : y + 2, :, :] *= 0.72
    return bg


def render_photo(
    pdf_bytes: bytes,
    p: PhotoParams,
    smudge_boxes: list[dict] | None = None,
    signature_anchor: tuple[int, float, float, float] | None = None,
) -> bytes:
    r = random.Random(p.seed ^ 0x5EED)
    nr = np.random.default_rng(p.seed)
    page = rasterize_pdf_page(pdf_bytes)
    page = page.filter(ImageFilter.GaussianBlur(0.5))  # print softness
    for b in smudge_boxes or []:
        page = _smudge(page, b, r)
    if signature_anchor is not None:
        _signature(page, signature_anchor, r)
    parr = np.asarray(page).astype(np.float32) * np.array([1.0, 0.985, 0.955], dtype=np.float32)
    if p.fold:
        fy = int(RASTER_H * r.uniform(0.3, 0.38))
        prof = np.exp(-(((np.arange(RASTER_H) - fy) / 10.0) ** 2)) * 0.13
        parr *= (1 - prof)[:, None, None]
    if p.coffee_ring:
        cx, cy, rad = RASTER_W * r.uniform(0.72, 0.86), RASTER_H * r.uniform(0.86, 0.93), RASTER_W * 0.07
        yy, xx = np.mgrid[0:RASTER_H, 0:RASTER_W]
        dist = np.sqrt((xx - cx) ** 2 + ((yy - cy) * 1.1) ** 2)
        ring = (np.exp(-(((dist - rad) / 4.0) ** 2)) * 0.35 + (dist < rad) * 0.05)[..., None]
        parr = parr * (1 - ring) + np.array([150, 110, 70], dtype=np.float32) * ring
    page = Image.fromarray(parr.clip(0, 255).astype(np.uint8))

    # warp page into the photo
    inv = _homography(page_quad(p), _raster_corners())
    coeffs = (inv / inv[2, 2]).flatten()[:8]
    warped = page.transform(
        (PHOTO_W, PHOTO_H), Image.Transform.PERSPECTIVE, tuple(coeffs), Image.Resampling.BICUBIC
    )
    mask = Image.new("L", page.size, 255).transform(
        (PHOTO_W, PHOTO_H), Image.Transform.PERSPECTIVE, tuple(coeffs), Image.Resampling.BILINEAR
    )
    quad = page_quad(p)
    shadow = Image.new("L", (PHOTO_W, PHOTO_H), 0)
    ImageDraw.Draw(shadow).polygon([(float(x) + 9, float(y) + 12) for x, y in quad], fill=255)
    shadow_a = np.asarray(shadow.filter(ImageFilter.GaussianBlur(14))).astype(np.float32)[..., None] / 255

    bg = _background(p, nr) * (1 - 0.5 * shadow_a)
    m = np.asarray(mask).astype(np.float32)[..., None] / 255
    img = bg * (1 - m) + np.asarray(warped).astype(np.float32) * m

    # uneven lighting: directional gradient + vignette
    yy, xx = np.mgrid[0:PHOTO_H, 0:PHOTO_W].astype(np.float32)
    nx, ny = xx / PHOTO_W - 0.5, yy / PHOTO_H - 0.5
    grad = (nx * math.cos(p.light_angle) + ny * math.sin(p.light_angle)) * 2 * p.light_strength
    vign = 1 - 0.30 * (nx**2 + ny**2) * 2
    img = img * (1.0 + grad - p.light_strength * 0.35)[..., None] * vign[..., None]
    img = img + nr.normal(0, 2.2, img.shape[:2]).astype(np.float32)[..., None]
    out = Image.fromarray(img.clip(0, 255).astype(np.uint8))
    out = out.filter(ImageFilter.GaussianBlur(p.blur))
    if p.motion:
        out = out.filter(ImageFilter.Kernel((3, 3), [0, 0, 0, 1, 1, 1, 0, 0, 0], scale=3))
    buf = io.BytesIO()
    out.save(buf, format="JPEG", quality=p.jpeg_quality, optimize=True, subsampling=2)
    return buf.getvalue()


def phash_hex(content: bytes, mime: str) -> str:
    """Perceptual hash (imagehash.phash, 64-bit hex) of page 1 of a PDF or of an image."""
    import imagehash

    img = rasterize_pdf_page(content) if mime == "application/pdf" else Image.open(io.BytesIO(content))
    return str(imagehash.phash(img.convert("L")))
