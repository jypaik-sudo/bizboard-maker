"""배경 제거 파이프라인.

순서:
  1. remove.bg API (type=product) — 제품 전용 segmentation, 주변 장식 배경 처리
  2. rembg 로컬 AI              — 폴백
"""
from __future__ import annotations
import io
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


def remove_background(
    image_bytes: bytes,
    api_key: str = "",
    anthropic_key: str = "",  # 호환성 유지 (미사용)
    subject_type: str = "product",  # "product" | "other" (로고·그래픽)
) -> bytes:
    # ── 1. remove.bg ─────────────────────────────────────────────────────────
    if api_key:
        try:
            resp = requests.post(
                "https://api.remove.bg/v1.0/removebg",
                files={"image_file": ("image.png", io.BytesIO(image_bytes))},
                data={"size": "auto", "type": subject_type},
                headers={"X-Api-Key": api_key},
                timeout=30,
            )
            if resp.status_code == 200:
                return resp.content
        except Exception:
            pass

    # ── 2. rembg 로컬 AI (폴백) ──────────────────────────────────────────────
    session = _get_session()
    if session:
        try:
            from rembg import remove
            return remove(image_bytes, session=session)
        except Exception:
            pass

    return image_bytes
