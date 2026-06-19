"""PNG 생성 엔진 — 1029×258 투명 배경"""
from __future__ import annotations
import io
import colorsys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageChops

CANVAS_W, CANVAS_H = 1029, 258
ASSETS = Path(__file__).parent.parent / "assets"

FONT_BOLD    = ASSETS / "Pretendard-Bold.otf"
FONT_REGULAR = ASSETS / "Pretendard-Regular.otf"

MAIN_PT      = 47   # 피그마 실측 47px
LEFT_MAIN_PT = 32
SUB_PT       = 39   # 피그마 실측 39px
BADGE_H      = 50   # 피그마: text-[24px] + py-[13px]*2 = 50px
GAP          = 20   # 카카오 비즈보드 가이드: 메인↔서브 간격 20px
LOGO_H       = 21   # 피그마 실측 (node 3470-381): inset top=9.3%*258=24, bottom=45 → h=21px
LOGO_PAD     = (50, 24)   # (right_margin, top) — 피그마: x=878, y=24, w≈101
BRAND_LOGO_H_DEFAULT = 65   # 브랜드 로고 기본 높이 (px) — 메인카피 역할 수행
BRAND_LOGO_H_MIN     = 35
BRAND_LOGO_H_MAX     = 120

# ABLY 로고 회피 영역: 우측 상단 (이모티콘 배치 시 제외)
_ABLY_SAFE_X = 830   # 이 x 좌표 이상 + y < 55 이면 ABLY 영역

MAIN_COLOR = (76, 76, 76)
SUB_COLOR  = (119, 119, 119)


# ── helpers ──────────────────────────────────────────────────────────────────

def _font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size)


def _hex(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _paste(canvas: Image.Image, img_bytes: bytes, box: tuple[int, int, int, int], rotation: float = 0.0) -> None:
    """contain-fit paste with transparency support."""
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    bw, bh = box[2] - box[0], box[3] - box[1]
    img.thumbnail((bw, bh), Image.LANCZOS)
    if rotation:
        img = img.rotate(-rotation, expand=True, resample=Image.BICUBIC)
    x = box[0] + (bw - img.width) // 2
    y = box[1] + (bh - img.height) // 2
    canvas.paste(img, (x, y), img.split()[3])


def _paste_logo(canvas: Image.Image, logo_bytes: bytes) -> None:
    logo = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")
    new_w = int(LOGO_H * logo.width / logo.height)
    logo = logo.resize((new_w, LOGO_H), Image.LANCZOS)
    x = CANVAS_W - new_w - LOGO_PAD[0]
    y = LOGO_PAD[1]
    canvas.paste(logo, (x, y), logo.split()[3])


def _trim_logo(img: Image.Image) -> Image.Image:
    """로고 배경 제거 + 여백 trim.

    Flood-fill (Photoshop 마술봉) 방식:
    - 네 모서리에서 연결된 배경 픽셀만 골라 투명화
    - 배경과 단절된 내부 픽셀(로고 글자 속 흰 부분 등)은 절대 건드리지 않음
    - 이미 부분 투명(remove.bg 처리 후)이면 잔류 흰 픽셀만 추가 정리
    """
    import numpy as np
    from PIL import ImageDraw

    img = img.convert("RGBA")
    arr = np.array(img)
    h, w = arr.shape[:2]

    # remove.bg 처리 결과: 이미 투명 픽셀이 있으면 잔류 흰 픽셀만 추가 제거
    if arr[:,:,3].min() < 10:
        lum = (0.299*arr[:,:,0].astype(float)
               + 0.587*arr[:,:,1]
               + 0.114*arr[:,:,2])
        arr[(lum > 245) & (arr[:,:,3] > 200), 3] = 0
        result = Image.fromarray(arr, "RGBA")
        bbox = result.split()[3].getbbox()
        return result.crop(bbox) if bbox else result

    # ── Flood-fill 배경 마스킹 ────────────────────────────────────────────
    # RGB 사본에 마커 색(0,255,0)으로 flood-fill → 채워진 영역 = 배경
    rgb = img.convert("RGB")
    temp = rgb.copy()
    MARKER = (0, 255, 0)
    THRESH = 50  # 안티앨리어싱·블러·크림색 배경 포함 허용 오차

    for corner in [(0, 0), (w-1, 0), (0, h-1), (w-1, h-1)]:
        try:
            ImageDraw.floodfill(temp, corner, MARKER, thresh=THRESH)
        except Exception:
            pass

    temp_arr = np.array(temp)
    # 마커 색과 정확히 일치하는 픽셀 = 배경
    bg_mask = (
        (temp_arr[:,:,0] == 0) &
        (temp_arr[:,:,1] == 255) &
        (temp_arr[:,:,2] == 0)
    )
    arr[bg_mask, 3] = 0

    result = Image.fromarray(arr, "RGBA")
    bbox = result.split()[3].getbbox()
    return result.crop(bbox) if bbox else result


def _paste_brand(canvas: Image.Image, brand_bytes: bytes, x: int, logo_h: int,
                  y: int | None = None, max_w: int | None = None) -> int:
    """브랜드 로고를 x, y 위치에 배치.
    logo_h: 목표 높이(px)로 항상 고정. y: 상단 y 좌표(None이면 캔버스 세로 중앙).
    max_w: 최대 허용 너비 — 초과 시 높이 유지하며 중앙 크롭.
    반환값: 실제 로고 너비(px).
    """
    img = _trim_logo(Image.open(io.BytesIO(brand_bytes)))
    natural_w = max(1, int(logo_h * img.width / img.height))
    actual_h = logo_h
    actual_w = natural_w
    # 높이 고정 리사이즈 먼저
    img = img.resize((actual_w, actual_h), Image.LANCZOS)
    # 너비가 max_w 초과 시 중앙 크롭 (높이 유지)
    if max_w and actual_w > max_w:
        crop_x = (actual_w - max_w) // 2
        img = img.crop((crop_x, 0, crop_x + max_w, actual_h))
        actual_w = max_w
    paste_y = (CANVAS_H - actual_h) // 2 if y is None else y
    canvas.paste(img, (x, paste_y), img.split()[3])
    return actual_w


def _dominant_color(img_bytes: bytes) -> tuple[int, int, int] | None:
    """상품 이미지에서 주요 색상 추출 (흰/검정 제외)."""
    try:
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB").resize((40, 40))
        quantized = img.quantize(colors=6)
        pal = quantized.getpalette()[:18]
        colors = [(pal[i], pal[i+1], pal[i+2]) for i in range(0, 18, 3)]
        def score(c: tuple) -> float:
            r, g, b = c
            brightness = (r + g + b) / 3
            saturation = max(r, g, b) - min(r, g, b)
            if brightness < 35 or brightness > 225:
                return 0
            return saturation
        best = max(colors, key=score)
        return best if score(best) > 20 else None
    except Exception:
        return None


def _harmonize_emoji(
    emoji_img: Image.Image,
    target_rgb: tuple[int, int, int] | None = None,
    strength: float = 0.28,
    hue_shift: float = 0.0,
) -> Image.Image:
    """이모티콘 색조를 target_rgb 방향으로 strength 비율만큼 이동.
    hue_shift != 0.0 이면 target_rgb 무시하고 H 채널을 hue_shift/360.0 만큼 이동."""
    emoji = emoji_img.convert("RGBA")
    pixels = list(emoji.getdata())
    new_pixels: list = []

    if hue_shift != 0.0:
        shift = hue_shift / 360.0
        for r, g, b, a in pixels:
            if a < 15:
                new_pixels.append((r, g, b, a))
                continue
            h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
            if s < 0.12 or v < 0.15:
                new_pixels.append((r, g, b, a))
                continue
            new_h = (h + shift) % 1.0
            nr, ng, nb = colorsys.hsv_to_rgb(new_h, s, v)
            new_pixels.append((int(nr * 255), int(ng * 255), int(nb * 255), a))
    else:
        if target_rgb is None:
            return emoji_img
        tr, tg, tb = (x / 255.0 for x in target_rgb)
        th, _ts, _tv = colorsys.rgb_to_hsv(tr, tg, tb)
        for r, g, b, a in pixels:
            if a < 15:
                new_pixels.append((r, g, b, a))
                continue
            h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
            if s < 0.12 or v < 0.15:
                new_pixels.append((r, g, b, a))
                continue
            diff = th - h
            if diff > 0.5:
                diff -= 1.0
            elif diff < -0.5:
                diff += 1.0
            new_h = (h + diff * strength) % 1.0
            nr, ng, nb = colorsys.hsv_to_rgb(new_h, s, v)
            new_pixels.append((int(nr * 255), int(ng * 255), int(nb * 255), a))

    result = Image.new("RGBA", emoji.size)
    result.putdata(new_pixels)
    return result


def _text_w(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    return draw.textbbox((0, 0), text, font=font)[2]


def _wrap_text(
    draw: ImageDraw.ImageDraw, text: str,
    font: ImageFont.FreeTypeFont, max_w: int,
) -> list[str]:
    """공백 기준으로 max_w 안에 들어오게 줄바꿈."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        if _text_w(draw, test, font) <= max_w:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text]


def _draw_badge(
    draw: ImageDraw.ImageDraw,
    x: int, y: int,
    text: str,
    color: tuple[int, int, int],
    font_size: int = 24,   # 피그마 실측 ~22-24px (서브카피 36px보다 작게)
) -> int:
    """Draw colored pill badge. Returns total width."""
    font = _font(True, font_size)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    px = 9    # 피그마: px-[9px]
    bw = tw + px * 2
    bh = BADGE_H   # 50px — 피그마: text-24px + py-13px*2
    draw.rounded_rectangle([x, y, x + bw, y + bh], radius=8, fill=color)
    draw.text(
        (x + px, y + (bh - th) // 2 - bbox[1]),
        text, font=font, fill=(255, 255, 255),
    )
    return bw


def _draw_text_block(
    draw: ImageDraw.ImageDraw,
    x: int, y_center: int,
    main_copy: str, sub_copy: str,
    emphasis_text: str = "",
    emphasis_color: str = "#CC0000",
    emphasis_type: str = "none",
    main_pt: int | None = None,
    sub_pt: int | None = None,
    center_w: int | None = None,    # 지정 시 [x, x+center_w] 가운데 정렬
    sub_anchor_x: int | None = None, # 지정 시 서브카피 좌측=sub_anchor_x, 메인은 서브 기준 가운데
) -> None:
    _main_pt = main_pt if main_pt is not None else MAIN_PT
    _sub_pt  = sub_pt  if sub_pt  is not None else SUB_PT

    f_main     = _font(True,  _main_pt)
    f_sub      = _font(False, _sub_pt)
    f_sub_bold = _font(True,  _sub_pt)
    em_rgb     = _hex(emphasis_color)

    has_sub = bool(sub_copy) or (emphasis_type != "none" and emphasis_text)
    _sub_h  = BADGE_H if (emphasis_type == "badge" and emphasis_text) else _sub_pt
    has_main = bool(main_copy)
    total_h = ((_main_pt + GAP) if has_main else 0) + (_sub_h if has_sub else 0)
    if not has_main and not has_sub:
        return
    y = y_center - total_h // 2

    # ── 서브카피 너비 사전 측정 (sub_anchor_x 모드용) ──
    if sub_anchor_x is not None:
        if emphasis_type == "badge" and emphasis_text:
            _bfont = _font(True, 24)
            _bbbox = draw.textbbox((0, 0), emphasis_text, font=_bfont)
            _bw = _bbbox[2] - _bbbox[0] + 9 * 2
            remaining = sub_copy.replace(emphasis_text, "", 1).strip(" ,·") if sub_copy else ""
            rem_w = _text_w(draw, remaining, f_sub) if remaining else 0
            _sub_w = _bw + (12 + rem_w if remaining else 0)
        elif emphasis_type == "text" and emphasis_text and sub_copy and emphasis_text in sub_copy:
            idx = sub_copy.index(emphasis_text)
            _sub_w = (_text_w(draw, sub_copy[:idx], f_sub)
                      + _text_w(draw, emphasis_text, f_sub_bold)
                      + _text_w(draw, sub_copy[idx + len(emphasis_text):], f_sub))
        else:
            _sub_w = _text_w(draw, sub_copy, f_sub) if sub_copy else 0
        # 메인카피 x: 서브카피 중심 기준 가운데 정렬
        _main_w = _text_w(draw, main_copy, f_main) if main_copy else 0
        _sub_center = sub_anchor_x + _sub_w // 2
        _main_x = _sub_center - _main_w // 2
    else:
        _sub_w = None
        _main_x = None

    def _cx(text: str, font) -> int:
        if sub_anchor_x is not None:
            return _main_x  # 서브카피 중심 기준 가운데
        if not center_w:
            return x
        tw = _text_w(draw, text, font)
        return x + max(0, (center_w - tw) // 2)

    if has_main:
        draw.text((_cx(main_copy, f_main), y), main_copy, font=f_main, fill=MAIN_COLOR)

    if not has_sub:
        return

    sub_y = y + ((_main_pt + GAP) if has_main else 0)
    # sub_anchor_x 모드: 서브카피 좌측 = sub_anchor_x
    _sub_start_x = sub_anchor_x if sub_anchor_x is not None else None

    if emphasis_type == "badge" and emphasis_text:
        remaining = sub_copy.replace(emphasis_text, "", 1).strip(" ,·") if sub_copy else ""
        rem_bbox = draw.textbbox((0, 0), remaining, font=f_sub) if remaining else (0, 0, 0, 0)
        rem_w = rem_bbox[2] - rem_bbox[0]
        _bfont = _font(True, 24)
        _bbbox = draw.textbbox((0, 0), emphasis_text, font=_bfont)
        _bw = _bbbox[2] - _bbbox[0] + 9 * 2
        total_sub_w = _bw + (12 + rem_w if remaining else 0)
        if _sub_start_x is not None:
            sub_x = _sub_start_x
        elif center_w:
            sub_x = x + max(0, (center_w - total_sub_w) // 2)
        else:
            sub_x = x
        badge_w = _draw_badge(draw, sub_x, sub_y, emphasis_text, em_rgb)
        cur_x = sub_x + badge_w + 12
        if remaining:
            rem_h = rem_bbox[3] - rem_bbox[1]
            rem_y = sub_y + (BADGE_H - rem_h) // 2 - rem_bbox[1]
            draw.text((cur_x, rem_y), remaining, font=f_sub, fill=SUB_COLOR)

    elif emphasis_type == "text" and emphasis_text and sub_copy and emphasis_text in sub_copy:
        idx    = sub_copy.index(emphasis_text)
        before = sub_copy[:idx]
        after  = sub_copy[idx + len(emphasis_text):]
        total_sub_w = (_text_w(draw, before, f_sub) + _text_w(draw, emphasis_text, f_sub_bold)
                       + _text_w(draw, after, f_sub))
        if _sub_start_x is not None:
            cur_x = _sub_start_x
        elif center_w:
            cur_x = x + max(0, (center_w - total_sub_w) // 2)
        else:
            cur_x = x
        if before:
            draw.text((cur_x, sub_y), before, font=f_sub, fill=SUB_COLOR)
            cur_x += _text_w(draw, before, f_sub)
        draw.text((cur_x, sub_y), emphasis_text, font=f_sub_bold, fill=em_rgb)
        cur_x += _text_w(draw, emphasis_text, f_sub_bold)
        if after:
            draw.text((cur_x, sub_y), after, font=f_sub, fill=SUB_COLOR)

    else:
        if sub_copy:
            sub_draw_x = _sub_start_x if _sub_start_x is not None else _cx(sub_copy, f_sub)
            draw.text((sub_draw_x, sub_y), sub_copy, font=f_sub, fill=SUB_COLOR)


def _fit_pt(draw: ImageDraw.ImageDraw, text: str, max_w: int, pt: int, min_pt: int = 20) -> int:
    """text가 max_w 안에 들어오는 최대 폰트 크기 (Bold 기준) 반환."""
    size = pt
    while size >= min_pt:
        if _text_w(draw, text, _font(True, size)) <= max_w:
            return size
        size -= 1
    return min_pt


def _draw_left_zone(
    draw: ImageDraw.ImageDraw,
    x: int, y_center: int,
    text: str, max_w: int,
    pt: int | None = None,
) -> None:
    """좌측 텍스트 존 — Bold 1줄 고정, 너비 초과 시 폰트 자동 축소."""
    if not text:
        return
    size = pt if pt is not None else LEFT_MAIN_PT
    size = _fit_pt(draw, text, max_w, size)
    font = _font(True, size)
    y = y_center - size // 2
    draw.text((x, y), text, font=font, fill=MAIN_COLOR)


# ── layout zones per format ───────────────────────────────────────────────────
#
# 피그마 실측 (1029×258 캔버스, 노드 3506-221 SKINFOOD 기준):
#   브랜드 로고 존:  x=5–175 (LEFT)
#   상품 오브젝트:   x=180–535 (CENTER)
#   카피 텍스트:     x=555–975 (RIGHT)
#   ABLY 로고:       x=878, y=24, w≈101, h≈21

# 두 텍스트 존 포맷 (좌=메인카피(좌) 텍스트 또는 없음, 우=메인카피(우)+서브카피)
CENTER_FMTS = {
    "가운데 오브젝트",
    "믹스 텍스트강조", "믹스 할인율뱃지",
    "로고 가운데+텍스트", "로고 가운데+뱃지",
}
# 로고 카테고리 (브랜드 로고 이미지 별도 존에 배치)
LOGO_FMTS = {
    "로고 가운데+텍스트", "로고 가운데+뱃지",
    "로고 우측+텍스트",   "로고 우측+뱃지",
}
# 로고 우측 전용 (브랜드로고 상단좌 + 상품 우측 + 카피 하단좌)
LOGO_RIGHT_FMTS = {"로고 우측+텍스트", "로고 우측+뱃지"}

ZONES = {
    # (obj_box, left_text_x|None, left_max_w, right_text_x|None, right_max_w)
    #
    # CENTER 계열: 오브젝트 캔버스 중앙 정렬 (center=515)
    # 좌우 text_x·max_w는 33px gap 보장
    #   left:  x=48,  max_w=284 → text 끝=332, obj_left=365, gap=33px ✓
    #   right: x=698, max_w=283 → 698+283=981, 우측 여백=48px ✓
    "가운데 오브젝트":    ((365, 5,  665, 253), 48,  284, 698, 283),
    "믹스 텍스트강조":    ((365, 5,  665, 253), 48,  284, 698, 283),
    "믹스 할인율뱃지":    ((365, 5,  665, 253), 48,  284, 698, 283),
    # 로고 가운데: 브랜드 로고(x=48, max_w=284) + 오브젝트(캔버스 중앙) + 우측 카피(698-)
    #   logo_right ≤ 332, obj_left=365 → gap≥33px ✓
    #   obj_right=665, right_x=698 → gap=33px ✓
    "로고 가운데+텍스트": ((365, 5,  665, 253), None, 0,   698, 283),
    "로고 가운데+뱃지":   ((365, 5,  665, 253), None, 0,   698, 283),

    # 우측 오브젝트 계열: 텍스트 좌측(x=48), 오브젝트 우측
    #   obj_left=650, text_x=48, 여유공간 충분
    "텍스트강조":         ((650, 10, 980, 248), 48,  560, None, 0),
    "할인율뱃지":         ((650, 10, 980, 248), 48,  560, None, 0),
    "서브텍스트강조":     ((650, 10, 980, 248), 48,  560, None, 0),

    # 로고 우측: 브랜드 로고(5-430 상단) + 오브젝트(440-730) + 카피 하단좌
    "로고 우측+텍스트":   ((440, 5,  730, 253), 20,  400, None, 0),
    "로고 우측+뱃지":     ((440, 5,  730, 253), 20,  400, None, 0),
}

# 브랜드 로고 이미지 배치 존 (LOGO_FMTS 전용)
BRAND_LOGO_ZONES: dict[str, tuple[int, int, int, int]] = {
    "로고 가운데+텍스트": (5, 15, 175, 243),   # 좌측 세로 전체
    "로고 가운데+뱃지":   (5, 15, 175, 243),
    "로고 우측+텍스트":   (5, 15, 430, 135),   # 상단 좌측 대형
    "로고 우측+뱃지":     (5, 15, 430, 135),
}


def _fmt_key(fmt: str) -> str:
    return (fmt
        .replace("[믹스] ", "믹스 ")
        .replace("[로고] ", "로고 "))


# ── main entry ────────────────────────────────────────────────────────────────

def generate_png(creative: dict, logo_bytes: bytes) -> bytes:
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    draw   = ImageDraw.Draw(canvas)

    fmt            = creative.get("format", "텍스트강조")
    main_copy      = creative.get("main_copy", "")
    sub_copy       = creative.get("sub_copy", "")
    sub_right      = creative.get("sub_right", "")
    emphasis_text  = creative.get("emphasis_text", "")
    emphasis_color = creative.get("emphasis_color", "#CC0000")
    emphasis_type  = creative.get("emphasis_type", "none")
    product_images = creative.get("product_images", [])
    emoji_images   = creative.get("emoji_images", [])
    brand_logo     = creative.get("brand_logo", None)

    adj        = creative.get("adjustments", {})
    _text_dx   = int(adj.get("text_dx",  0))
    _text_dy   = int(adj.get("text_dy",  0))   # 현재 UI에서 제거됨, 하위 호환
    _left_dx   = int(adj.get("left_dx",  0))   # CENTER_FMTS 메인카피(좌) X
    _right_dx  = int(adj.get("right_dx", 0))   # CENTER_FMTS 메인카피(우) X
    _main_size  = int(adj.get("main_size", MAIN_PT))
    _sub_size   = int(adj.get("sub_size",  SUB_PT))
    _logo_size  = max(BRAND_LOGO_H_MIN, min(BRAND_LOGO_H_MAX, int(adj.get("logo_size", BRAND_LOGO_H_DEFAULT))))
    _obj_dx     = int(adj.get("obj_dx",   0))
    _obj_dy     = int(adj.get("obj_dy",   0))
    _obj_rot   = float(adj.get("obj_rotation", 0.0))
    _obj_scale = float(adj.get("obj_scale", 100)) / 100.0
    _em_size   = int(adj.get("em_size",  52))
    _em_hue    = float(adj.get("em_hue", 0.0))

    key = _fmt_key(fmt)
    obj_box, text_x, _lw, right_x, _rw = ZONES.get(key, ZONES["텍스트강조"])

    # obj_scale 적용 (박스 중심 고정, 비율 조정)
    if obj_box and _obj_scale != 1.0:
        cx = (obj_box[0] + obj_box[2]) // 2
        cy = (obj_box[1] + obj_box[3]) // 2
        hw = int((obj_box[2] - obj_box[0]) * _obj_scale / 2)
        hh = int((obj_box[3] - obj_box[1]) * _obj_scale / 2)
        obj_box = (cx - hw, cy - hh, cx + hw, cy + hh)

    # obj_box offset 적용
    if obj_box and (_obj_dx or _obj_dy):
        obj_box = (obj_box[0]+_obj_dx, obj_box[1]+_obj_dy,
                   obj_box[2]+_obj_dx, obj_box[3]+_obj_dy)

    # 1. 이미지 오브젝트 배치
    _MIN_GAP = 33  # 로고 우측 ↔ 오브젝트 좌측 최소 간격

    # 로고 우측: logo+서브카피 블록 세로 중앙 정렬
    _logo_block_h = _logo_size + GAP + _sub_size
    _logo_y_right = max(10, CANVAS_H // 2 - _logo_block_h // 2)
    # 로고 가운데: 로고 단독 캔버스 세로 중앙 정렬 (서브카피는 우측 별도 존)
    _logo_y_center = (CANVAS_H - _logo_size) // 2

    if key in LOGO_RIGHT_FMTS:
        # 브랜드 로고 → 좌측 x=48+text_dx (메인카피 대체, text_dx로 이동)
        _logo_y = _logo_y_right
        _logo_x = 48 + _text_dx
        if brand_logo:
            obj_left = obj_box[0] if obj_box else CANVAS_W
            _logo_max_w = max(1, obj_left - _logo_x - _MIN_GAP)
            _paste_brand(canvas, brand_logo, _logo_x, _logo_size, y=_logo_y, max_w=_logo_max_w)
        # 상품 → 우측 존
        if obj_box and product_images:
            _paste(canvas, product_images[0], obj_box, rotation=_obj_rot)

    elif key in LOGO_FMTS:
        # 브랜드 로고 → 좌측 x=48+left_dx (메인카피(좌) 역할, left_dx로 이동)
        _logo_y = _logo_y_center
        _logo_x = 48 + _left_dx
        if brand_logo:
            obj_left = obj_box[0] if obj_box else CANVAS_W
            _logo_max_w = max(1, obj_left - _logo_x - _MIN_GAP)
            _paste_brand(canvas, brand_logo, _logo_x, _logo_size, y=_logo_y, max_w=_logo_max_w)
        # 상품 → 가운데 존
        if obj_box and product_images:
            _paste(canvas, product_images[0], obj_box, rotation=_obj_rot)

    elif obj_box:
        # 일반 포맷 (가운데 오브젝트 / 텍스트강조 계열 우측 존 포함)
        if product_images:
            n = min(len(product_images), 3)
            if n == 1:
                _paste(canvas, product_images[0], obj_box, rotation=_obj_rot)
            else:
                bw    = obj_box[2] - obj_box[0]
                sub_w = bw // n
                for i in range(n):
                    sub_box = (
                        obj_box[0] + sub_w * i, obj_box[1],
                        obj_box[0] + sub_w * (i + 1), obj_box[3],
                    )
                    _paste(canvas, product_images[i], sub_box, rotation=_obj_rot)

    # 2. 이모티콘 — 개별 설정 지원
    raw_emoji_items = creative.get("emoji_items", [])  # [{"bytes": b, "size": 52, "hue": 0, "rotation": 15}, ...]
    if not raw_emoji_items and emoji_images:
        raw_emoji_items = [{"bytes": b, "size": _em_size, "hue": _em_hue, "rotation": 0}
                           for b in emoji_images]

    if raw_emoji_items and obj_box:
        _palette_src = product_images[0] if product_images else (brand_logo or None)
        _palette = _dominant_color(_palette_src) if _palette_src else None
        x0, y0, x1, y1 = obj_box

        # 3위치 계산
        def _em_pos(size, idx, positions_taken):
            candidates = [
                (x1 - size - 8,  y0 + 8),            # 우상
                (x0 + 8,         y1 - size - 8),      # 좌하
                (x1 - size - 8,  y1 - size - 8),      # 우하
                (x0 + 8,         y0 + 8),              # 좌상
            ]
            for pos in candidates:
                px, py = pos
                # ABLY 회피
                if px + size > _ABLY_SAFE_X and py < 55:
                    continue
                # 이미 사용된 위치와 겹치지 않도록
                if all(abs(px-tx) > size//2 or abs(py-ty) > size//2 for tx,ty in positions_taken):
                    return pos
            return candidates[idx % len(candidates)]

        positions_taken = []
        for item in raw_emoji_items[:3]:
            eb = item.get("bytes") if isinstance(item, dict) else item
            if not eb:
                continue
            i_size = int(item.get("size", _em_size) if isinstance(item, dict) else _em_size)
            i_hue  = float(item.get("hue",  _em_hue) if isinstance(item, dict) else _em_hue)
            i_rot  = float(item.get("rotation", 0)   if isinstance(item, dict) else 0)
            pos = _em_pos(i_size, len(positions_taken), positions_taken)
            positions_taken.append(pos)
            try:
                em = Image.open(io.BytesIO(eb)).convert("RGBA").resize((i_size, i_size), Image.LANCZOS)
                if i_hue != 0.0 or _palette:
                    em = _harmonize_emoji(em, _palette if i_hue == 0.0 else None,
                                          hue_shift=i_hue)
                if i_rot:
                    em = em.rotate(-i_rot, expand=True, resample=Image.BICUBIC)
                canvas.paste(em, pos, em.split()[3])
            except Exception:
                pass

    # 3. 텍스트 블록
    if key in LOGO_RIGHT_FMTS:
        # 로고가 메인카피 대체 → 서브카피만 로고 아래 20px 간격으로 배치
        logo_bottom = _logo_y + _logo_size + GAP
        if sub_copy:
            _sub_h = BADGE_H if (emphasis_type == "badge" and emphasis_text) else _sub_size
            _draw_text_block(
                draw, 48 + _text_dx, logo_bottom + _sub_h // 2,
                "", sub_copy,
                emphasis_text, emphasis_color, emphasis_type,
                main_pt=_main_size, sub_pt=_sub_size,
            )

    elif key in LOGO_FMTS:
        # 로고가 좌측 메인카피(좌) 대체 → 우측에만 서브카피
        if right_x and (sub_copy or sub_right):
            _draw_text_block(
                draw, right_x + _right_dx, CANVAS_H // 2,
                sub_copy, sub_right,
                emphasis_text, emphasis_color, emphasis_type,
                main_pt=_main_size, sub_pt=_sub_size,
            )

    elif key in CENTER_FMTS:
        # 좌측 필요 크기 계산 → 좌·우 동기화 (메인카피 좌·우 항상 같은 크기)
        effective_pt = _main_size
        if text_x is not None and main_copy:
            effective_pt = _fit_pt(draw, main_copy, _lw, _main_size)
        # 우측 필요 크기도 체크해서 더 작은 쪽을 기준으로
        if right_x and sub_copy and _rw > 0:
            right_pt = _fit_pt(draw, sub_copy, _rw, _main_size)
            effective_pt = min(effective_pt, right_pt)

        if text_x is not None and main_copy:
            _draw_left_zone(draw, text_x + _left_dx, CANVAS_H // 2, main_copy, _lw, pt=effective_pt)
        if right_x and (sub_copy or sub_right):
            _draw_text_block(
                draw, right_x + _right_dx, CANVAS_H // 2,
                sub_copy, sub_right,
                emphasis_text, emphasis_color, emphasis_type,
                main_pt=effective_pt, sub_pt=_sub_size,
                center_w=_rw if key in CENTER_FMTS else None,
            )

    else:
        # 단일 존 (텍스트강조 / 할인율뱃지 / 서브텍스트강조)
        if main_copy or sub_copy:
            # 서브텍스트강조: X=0 기준 서브카피 좌측=48px, 메인카피는 서브 기준 가운데 정렬
            _draw_text_block(
                draw, text_x, CANVAS_H // 2 + _text_dy,
                main_copy, sub_copy,
                emphasis_text, emphasis_color, emphasis_type,
                main_pt=_main_size, sub_pt=_sub_size,
                sub_anchor_x=(48 + _text_dx) if key == "서브텍스트강조" else None,
                center_w=None if key == "서브텍스트강조" else None,
            )

    # 4. ABLY 로고 — 항상 우측 상단
    if logo_bytes:
        _paste_logo(canvas, logo_bytes)

    buf = io.BytesIO()
    canvas.save(buf, "PNG")
    return buf.getvalue()
