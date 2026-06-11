"""배경 제거: rembg(로컬 AI) → remove.bg API → 원본 순서로 시도."""
from __future__ import annotations
import requests
import io

_rembg_session = None


def _get_session():
    global _rembg_session
    if _rembg_session is None:
        try:
            from rembg import new_session
            _rembg_session = new_session("u2netp")   # 경량 모델 (~4MB)
        except Exception:
            _rembg_session = False   # 설치 실패 sentinel
    return _rembg_session or None


def remove_background(image_bytes: bytes, api_key: str = "") -> bytes:
    # 1. rembg 로컬 AI (API 키 불필요)
    session = _get_session()
    if session:
        try:
            from rembg import remove
            return remove(image_bytes, session=session)
        except Exception:
            pass

    # 2. remove.bg API (키가 있는 경우)
    if api_key:
        try:
            resp = requests.post(
                "https://api.remove.bg/v1.0/removebg",
                files={"image_file": ("image.png", io.BytesIO(image_bytes))},
                data={"size": "auto"},
                headers={"X-Api-Key": api_key},
                timeout=30,
            )
            if resp.status_code == 200:
                return resp.content
        except Exception:
            pass

    return image_bytes
