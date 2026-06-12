"""오브젝트 이미지에서 대표 색상 추출 → 채도 부스트해 강조색 반환."""
from __future__ import annotations
import io
import colorsys


def extract_vibrant_color(image_bytes: bytes) -> str:
    """상품 이미지에서 대표 색상 추출 후 채도·명도 조정해 HEX 반환.

    - 투명/무채색 픽셀 제거 후 지배적 색조(hue) 추출
    - 채도(S) 최소 0.85 보장 → 네이비도 쨍한 파란색으로
    - 명도(V) 0.45~0.75 범위 클램프 → 가독성 확보
    """
    try:
        import numpy as np
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        img = img.resize((64, 64), Image.LANCZOS)
        arr = np.array(img, dtype=float)

        # 투명 픽셀 제거
        alpha_mask = arr[:, :, 3] > 128
        pixels = arr[alpha_mask][:, :3] / 255.0  # (N, 3) float RGB

        if len(pixels) < 10:
            return "#CC0000"

        # HSV 변환
        hsv = np.array([colorsys.rgb_to_hsv(r, g, b) for r, g, b in pixels])

        # 유채색만 (채도 > 0.15, 명도 > 0.1 and < 0.95)
        color_mask = (hsv[:, 1] > 0.15) & (hsv[:, 2] > 0.10) & (hsv[:, 2] < 0.95)
        colored = hsv[color_mask]

        if len(colored) < 5:
            # 유채색이 거의 없으면 전체 픽셀 중 가장 채도 높은 것
            colored = hsv[np.argsort(hsv[:, 1])[-max(1, len(hsv)//5):]]

        # 색조(hue)를 12 버킷으로 나눠 최다 버킷 찾기
        N_BUCKETS = 12
        hue_buckets = (colored[:, 0] * N_BUCKETS).astype(int) % N_BUCKETS
        bucket_counts = np.bincount(hue_buckets, minlength=N_BUCKETS)
        dominant = int(np.argmax(bucket_counts))

        bucket_pixels = colored[hue_buckets == dominant]

        avg_h = float(np.mean(bucket_pixels[:, 0]))
        raw_s = float(np.mean(bucket_pixels[:, 1]))
        raw_v = float(np.mean(bucket_pixels[:, 2]))

        # 채도 부스트: 원본 × 1.6, 최소 0.85 보장
        s_boosted = min(1.0, max(0.85, raw_s * 1.6))
        # 명도 클램프: 너무 어둡거나 너무 밝으면 가독성 저하
        v_adj = max(0.45, min(0.75, raw_v))

        r, g, b = colorsys.hsv_to_rgb(avg_h, s_boosted, v_adj)
        return "#{:02X}{:02X}{:02X}".format(int(r * 255), int(g * 255), int(b * 255))

    except Exception:
        return "#CC0000"
