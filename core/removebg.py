"""배경 제거 파이프라인.

순서:
  1. Claude Vision 스마트 크롭  — 메인 상품 bbox 감지, 주변 장식 제거
  2. remove.bg API (type=product) — 제품 전용 segmentation
  3. rembg 로컬 AI              — 폴백
"""
from __future__ import annotations
import io
import json
import base64
import requests

_rembg_session = None


def _get_session():
    global _rembg_session
    if _rembg_session is None:
        try:
            from rembg import new_session
            _rembg_session = new_session("u2netp")
        except Exception:
            _rembg_session = False
    return _rembg_session or None


def _has_floating_decorations(b64: str, anthropic_client) -> bool:
    """이미지에 상품과 분리된 부유 장식(이모티콘·스티커·워터마크)이 있는지 판단."""
    try:
        msg = anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image",
                     "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                    {"type": "text",
                     "text": (
                         "Does this image contain floating decorative elements "
                         "(emoji, stickers, character icons, illustrated decorations) "
                         "that are SEPARATE from the main product and placed around it? "
                         "Answer only YES or NO."
                     )},
                ],
            }],
        )
        return "YES" in msg.content[0].text.upper()
    except Exception:
        return False


def _crop_to_product(image_bytes: bytes, b64: str, w: int, h: int, anthropic_client) -> bytes:
    """부유 장식 제외, 메인 상품 전체를 포함하는 bbox로 크롭."""
    try:
        msg = anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=120,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image",
                     "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                    {"type": "text",
                     "text": (
                         f"Image size: {w}x{h}px. "
                         "Return a bounding box that contains ALL parts of the main product(s). "
                         "Be VERY generous — include the full extent of every item that is part "
                         "of the main subject. Exclude ONLY floating stickers/emoji around the edges. "
                         'Reply ONLY with JSON: {"x1":N,"y1":N,"x2":N,"y2":N}. No other text.'
                     )},
                ],
            }],
        )
        raw = msg.content[0].text.strip()
        start, end = raw.index("{"), raw.rindex("}") + 1
        data = json.loads(raw[start:end])

        pad = max(20, int(min(w, h) * 0.05))
        x1 = max(0, int(data["x1"]) - pad)
        y1 = max(0, int(data["y1"]) - pad)
        x2 = min(w, int(data["x2"]) + pad)
        y2 = min(h, int(data["y2"]) + pad)

        if (x2 - x1) < 40 or (y2 - y1) < 40:
            return image_bytes

        from PIL import Image as _Image
        img = _Image.open(io.BytesIO(image_bytes)).convert("RGB")
        cropped = img.crop((x1, y1, x2, y2))
        out = io.BytesIO()
        cropped.save(out, format="PNG")
        return out.getvalue()
    except Exception:
        return image_bytes


def _smart_crop(image_bytes: bytes, anthropic_key: str) -> bytes:
    """부유 장식 감지 시에만 크롭 적용. 일반 상품샷은 원본 유지."""
    try:
        import anthropic
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = img.size

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        b64 = base64.standard_b64encode(buf.getvalue()).decode()

        client = anthropic.Anthropic(api_key=anthropic_key)

        # 1단계: 장식 여부 판단
        if not _has_floating_decorations(b64, client):
            return image_bytes  # 깨끗한 상품샷 → 크롭 없이 바로 bg 제거

        # 2단계: 장식 있을 때만 크롭
        return _crop_to_product(image_bytes, b64, w, h, client)

    except Exception:
        return image_bytes


def remove_background(
    image_bytes: bytes,
    api_key: str = "",
    anthropic_key: str = "",
) -> bytes:
    # ── 1. Claude Vision 스마트 크롭 ─────────────────────────────────────────
    if anthropic_key:
        image_bytes = _smart_crop(image_bytes, anthropic_key)

    # ── 2. remove.bg (type=product) ──────────────────────────────────────────
    if api_key:
        try:
            resp = requests.post(
                "https://api.remove.bg/v1.0/removebg",
                files={"image_file": ("image.png", io.BytesIO(image_bytes))},
                data={"size": "auto", "type": "product"},
                headers={"X-Api-Key": api_key},
                timeout=30,
            )
            if resp.status_code == 200:
                return resp.content
        except Exception:
            pass

    # ── 3. rembg 로컬 AI (폴백) ──────────────────────────────────────────────
    session = _get_session()
    if session:
        try:
            from rembg import remove
            return remove(image_bytes, session=session)
        except Exception:
            pass

    return image_bytes
