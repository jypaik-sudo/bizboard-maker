"""PNG 생성 엔진 — 1029×258 투명 배경"""
from __future__ import annotations
import io
import colorsys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

CANVAS_W, CANVAS_H = 1029, 258
ASSETS = Path(__file__).parent.parent / "assets"

FONT_BOLD    = ASSETS / "Pretendard-Bold.otf"
FONT_REGULAR = ASSETS / "Pretendard-Regular.otf"

MAIN_PT      = 47   # 피그마 실측 47px
LEFT_MAIN_PT = 32
SUB_PT       = 39   # 피그마 실측 39px
BADGE_H      = 50   # 피그마: text-[24px] + py-[13px]*2 = 50px
GAP          = 14   # 피그마: sub_y(138) - main_y(77) - main_h(47) ≈ 14px
LOGO_H       = 24   # ABLY 로고 높이 (피그마 실측 21px, 가시성 고려 24px)
LOGO_PAD     = (50, 24)   # (right_margin, top) — 피그마: x=878, y=24, w≈101

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


def _paste(canvas: Image.Image, img_bytes: bytes, box: tuple[int, int, int, int]) -> None:
    """contain-fit paste with transparency support."""
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    bw, bh = box[2] - box[0], box[3] - box[1]
    img.thumbnail((bw, bh), Image.LANCZOS)
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
    target_rgb: tuple[int, int, int],
    strength: float = 0.28,
) -> Image.Image:
    """이모티콘 색조를 target_rgb 방향으로 strength 비율만큼 이동."""
    tr, tg, tb = (x / 255.0 for x in target_rgb)
    th, _ts, _tv = colorsys.rgb_to_hsv(tr, tg, tb)

    emoji = emoji_img.convert("RGBA")
    pixels = list(emoji.getdata())
    new_pixels: list = []

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
) -> None:
    f_main     = _font(True,  MAIN_PT)
    f_sub      = _font(False, SUB_PT)
    f_sub_bold = _font(True,  SUB_PT)
    em_rgb     = _hex(emphasis_color)

    has_sub = bool(sub_copy) or (emphasis_type != "none" and emphasis_text)
    _sub_h  = BADGE_H if (emphasis_type == "badge" and emphasis_text) else SUB_PT
    total_h = MAIN_PT + (GAP + _sub_h if has_sub else 0)
    y = y_center - total_h // 2

    if main_copy:
        draw.text((x, y), main_copy, font=f_main, fill=MAIN_COLOR)

    if not has_sub:
        return

    sub_y = y + MAIN_PT + GAP

    if emphasis_type == "badge" and emphasis_text:
        badge_w = _draw_badge(draw, x, sub_y, emphasis_text, em_rgb)
        cur_x = x + badge_w + 12
        remaining = sub_copy.replace(emphasis_text, "", 1).strip(" ,·") if sub_copy else ""
        if remaining:
            # 배지 높이(SUB_PT) 기준으로 텍스트 세로 가운데 정렬
            rem_bbox = draw.textbbox((0, 0), remaining, font=f_sub)
            rem_h = rem_bbox[3] - rem_bbox[1]
            rem_y = sub_y + (BADGE_H - rem_h) // 2 - rem_bbox[1]
            draw.text((cur_x, rem_y), remaining, font=f_sub, fill=SUB_COLOR)

    elif emphasis_type == "text" and emphasis_text and sub_copy and emphasis_text in sub_copy:
        idx    = sub_copy.index(emphasis_text)
        before = sub_copy[:idx]
        after  = sub_copy[idx + len(emphasis_text):]
        cur_x  = x
        if before:
            draw.text((cur_x, sub_y), before, font=f_sub, fill=SUB_COLOR)
            cur_x += _text_w(draw, before, f_sub)
        draw.text((cur_x, sub_y), emphasis_text, font=f_sub_bold, fill=em_rgb)
        cur_x += _text_w(draw, emphasis_text, f_sub_bold)
        if after:
            draw.text((cur_x, sub_y), after, font=f_sub, fill=SUB_COLOR)

    else:
        if sub_copy:
            draw.text((x, sub_y), sub_copy, font=f_sub, fill=SUB_COLOR)


def _draw_left_zone(
    draw: ImageDraw.ImageDraw,
    x: int, y_center: int,
    text: str, max_w: int,
) -> None:
    """좌측 텍스트 존 — LEFT_MAIN_PT Bold, 공백 기준 줄바꿈, 세로 가운데 정렬."""
    if not text:
        return
    font = _font(True, LEFT_MAIN_PT)
    lines = _wrap_text(draw, text, font, max_w)
    line_h = LEFT_MAIN_PT + 6
    total_h = len(lines) * line_h - 6
    y = y_center - total_h // 2
    for line in lines:
        draw.text((x, y), line, font=font, fill=MAIN_COLOR)
        y += line_h


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
    "가운데 오브젝트":    ((180, 5,  535, 253), 20,   150, 555, 445),
    "텍스트강조":         ((650, 10, 1010, 248), 55,  560, None, 0),
    "할인율뱃지":         ((650, 10, 1010, 248), 55,  560, None, 0),
    "서브텍스트강조":     ((650, 10, 1010, 248), 55,  560, None, 0),
    "믹스 텍스트강조":    ((180, 5,  535, 253), 20,   150, 555, 445),
    "믹스 할인율뱃지":    ((180, 5,  535, 253), 20,   150, 555, 445),
    "로고 가운데+텍스트": ((180, 5,  535, 253), None, 0,   555, 445),
    "로고 가운데+뱃지":   ((180, 5,  535, 253), None, 0,   555, 445),
    "로고 우측+텍스트":   ((440, 5,  730, 253), 20,   400, None, 0),
    "로고 우측+뱃지":     ((440, 5,  730, 253), 20,   400, None, 0),
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

    key = _fmt_key(fmt)
    obj_box, text_x, _lw, right_x, _rw = ZONES.get(key, ZONES["텍스트강조"])

    # 1. 이미지 오브젝트 배치
    if key in LOGO_RIGHT_FMTS:
        # 브랜드 로고 → 상단 좌측 존
        blz = BRAND_LOGO_ZONES.get(key)
        if blz and brand_logo:
            _paste(canvas, brand_logo, blz)
        # 상품 → 우측 존
        if obj_box and product_images:
            _paste(canvas, product_images[0], obj_box)

    elif key in LOGO_FMTS:
        # 브랜드 로고 → 좌측 존
        blz = BRAND_LOGO_ZONES.get(key)
        if blz and brand_logo:
            _paste(canvas, brand_logo, blz)
        # 상품 → 가운데 존
        if obj_box and product_images:
            _paste(canvas, product_images[0], obj_box)

    elif obj_box:
        # 일반 포맷 (가운데 오브젝트 / 텍스트강조 계열 우측 존 포함)
        if product_images:
            n = min(len(product_images), 3)
            if n == 1:
                _paste(canvas, product_images[0], obj_box)
            else:
                bw    = obj_box[2] - obj_box[0]
                sub_w = bw // n
                for i in range(n):
                    sub_box = (
                        obj_box[0] + sub_w * i, obj_box[1],
                        obj_box[0] + sub_w * (i + 1), obj_box[3],
                    )
                    _paste(canvas, product_images[i], sub_box)

    # 2. 이모티콘 — 대각 배치 (상품 주변), ABLY 로고 회피
    if emoji_images and obj_box:
        _palette_src = product_images[0] if product_images else (brand_logo or None)
        _palette = _dominant_color(_palette_src) if _palette_src else None
        em_size = 52
        x0, y0, x1, y1 = obj_box

        # 위치 1: 상단 우측 — ABLY 영역(x>830, y<55)이면 상단 좌측으로
        p1x = x1 - em_size - 8
        p1y = y0 + 8
        if p1x + em_size > _ABLY_SAFE_X and p1y < 55:
            p1x = x0 + 8   # 상단 좌측으로 이동

        # 위치 2: 하단 반대편 (위치1이 우측이면 하단 좌측, 좌측이면 하단 우측)
        if p1x == x0 + 8:
            p2x = x1 - em_size - 8
        else:
            p2x = x0 + 8
        p2y = y1 - em_size - 8

        em_positions = [(p1x, p1y), (p2x, p2y)]

        for pos, eb in zip(em_positions, emoji_images[:2]):
            try:
                em = Image.open(io.BytesIO(eb)).convert("RGBA").resize(
                    (em_size, em_size), Image.LANCZOS
                )
                if _palette:
                    em = _harmonize_emoji(em, _palette)
                canvas.paste(em, pos, em.split()[3])
            except Exception:
                pass

    # 3. 텍스트 블록
    if key in LOGO_RIGHT_FMTS:
        # 브랜드 로고는 상단 좌측, 카피는 하단 좌측
        text_y = CANVAS_H * 3 // 4   # ≈ 194px
        if main_copy or sub_copy:
            _draw_text_block(
                draw, text_x, text_y,
                main_copy, sub_copy,
                emphasis_text, emphasis_color, emphasis_type,
            )

    elif key in CENTER_FMTS:
        # 좌측 존: 메인카피(좌) 텍스트 — 로고 가운데는 None이므로 스킵
        if text_x is not None and main_copy:
            _draw_left_zone(draw, text_x, CANVAS_H // 2, main_copy, _lw)
        # 우측 존: 메인카피(우) + 서브카피
        if right_x and (sub_copy or sub_right):
            _draw_text_block(
                draw, right_x, CANVAS_H // 2,
                sub_copy, sub_right,
                emphasis_text, emphasis_color, emphasis_type,
            )

    else:
        # 단일 존 (텍스트강조 / 할인율뱃지 / 서브텍스트강조)
        if main_copy or sub_copy:
            _draw_text_block(
                draw, text_x, CANVAS_H // 2,
                main_copy, sub_copy,
                emphasis_text, emphasis_color, emphasis_type,
            )

    # 4. ABLY 로고 — 항상 우측 상단
    if logo_bytes:
        _paste_logo(canvas, logo_bytes)

    buf = io.BytesIO()
    canvas.save(buf, "PNG")
    return buf.getvalue()
