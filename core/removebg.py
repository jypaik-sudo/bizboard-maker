import requests
import io


def remove_background(image_bytes: bytes, api_key: str) -> bytes:
    """remove.bg API로 배경 제거. 실패 시 원본 반환."""
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
