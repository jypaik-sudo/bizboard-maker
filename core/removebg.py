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


def _smart_crop(image_bytes: bytes, anthropic_key: str) -> bytes:
    """Claude Haiku로 메인 상품 bounding box 감지 → 타이트 크롭.

    - 주변 이모티콘·스티커·워터마크 자동 제외
    - 감지 실패 시 원본 반환 (파이프라인 중단 없음)
    """
    try:
        import anthropic
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = img.size

        # JPEG 압축으로 API 전송 크기 축소
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        b64 = base64.standard_b64encode(buf.getvalue()).decode()

        client = anthropic.Anthropic(api_key=anthropic_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=120,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
                    },
                    {
                        "type": "text",
                        "text": (
                            f"Image size: {w}x{h}px. "
                            "Find a bounding box that FULLY contains the main product — "
                            "include every part of it (edges, shadows, accessories attached to it). "
                            "Be GENEROUS, not tight. "
                            "Only exclude elements that are clearly SEPARATE floating decorations "
                            "(emoji, stickers, watermarks) that do NOT touch the product. "
                            "If no such decorations exist, return the full image bounds. "
                            'Reply ONLY with JSON: {"x1":N,"y1":N,"x2":N,"y2":N}. No other text.'
                        ),
                    },
                ],
            }],
        )

        raw = msg.content[0].text.strip()
        start, end = raw.index("{"), raw.rindex("}") + 1
        data = json.loads(raw[start:end])

        # 비율 기반 패딩: 이미지 짧은 변의 4%
        pad = max(20, int(min(w, h) * 0.04))
        x1 = max(0, int(data["x1"]) - pad)
        y1 = max(0, int(data["y1"]) - pad)
        x2 = min(w, int(data["x2"]) + pad)
        y2 = min(h, int(data["y2"]) + pad)

        # 크롭 면적이 원본의 75% 이상이면 장식이 없는 깔끔한 상품샷 → 크롭 생략
        crop_area = (x2 - x1) * (y2 - y1)
        orig_area = w * h
        if crop_area / orig_area >= 0.75 or (x2 - x1) < 40 or (y2 - y1) < 40:
            return image_bytes

        cropped = img.crop((x1, y1, x2, y2))
        out = io.BytesIO()
        cropped.save(out, format="PNG")
        return out.getvalue()

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
