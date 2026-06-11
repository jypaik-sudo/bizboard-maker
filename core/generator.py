"""PNG 생성 엔진 — 1029×258 투명 배경"""
from __future__ import annotations
import io
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

CANVAS_W, CANVAS_H = 1029, 258
ASSETS = Path(__file__).parent.parent / "assets"

FONT_BOLD    = ASSETS / "Pretendard-Bold.otf"
FONT_REGULAR = ASSETS / "Pretendard-Regular.otf"

MAIN_PT   = 45
SUB_PT    = 36
GAP       = 20   # main ↔ sub
LOGO_H    = 38
LOGO_PAD  = (20, 14)   # right, top

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


def _text_w(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    return draw.textbbox((0, 0), text, font=font)[2]


def _draw_badge(
    draw: ImageDraw.ImageDraw,
    x: int, y: int,
    text: str,
    color: tuple[int, int, int],
    font_size: int = SUB_PT - 4,
) -> int:
    """Draw colored pill badge. Returns total width."""
    font = _font(True, font_size)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    px, py = 12, 6
    bw = tw + px * 2
    bh = SUB_PT
    draw.rounded_rectangle([x, y, x + bw, y + bh], radius=7, fill=color)
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
    emphasis_type: str = "none",   # "text" | "badge" | "none"
) -> None:
    f_main     = _font(True,  MAIN_PT)
    f_sub      = _font(False, SUB_PT)
    f_sub_bold = _font(True,  SUB_PT)
    em_rgb     = _hex(emphasis_color)

    has_sub = bool(sub_copy) or (emphasis_type != "none" and emphasis_text)
    total_h = MAIN_PT + (GAP + SUB_PT if has_sub else 0)
    y = y_center - total_h // 2

    # Main copy
    if main_copy:
        draw.text((x, y), main_copy, font=f_main, fill=MAIN_COLOR)

    if not has_sub:
        return

    sub_y = y + MAIN_PT + GAP

    # Sub copy with optional emphasis
    if emphasis_type == "badge" and emphasis_text:
        badge_w = _draw_badge(draw, x, sub_y, emphasis_text, em_rgb)
        cur_x = x + badge_w + 12
        if sub_copy:
            draw.text((cur_x, sub_y), sub_copy, font=f_sub, fill=SUB_COLOR)

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


# ── layout zones per format ───────────────────────────────────────────────────

PAD = 20   # general inner padding

# center-object formats: draw main_copy LEFT, sub_copy+sub_right RIGHT
CENTER_FMTS = {"가운데 오브젝트", "로고 가운데+텍스트", "로고 가운데+뱃지"}

ZONES = {
    # (obj_box, left_text_x, left_max_w, right_text_x_or_None, right_max_w)
    "가운데 오브젝트":    ((340, PAD, 690, CANVAS_H - PAD), 55, 265, 710, 210),
    "텍스트강조":         (None,                            55, 860, None, 0),
    "할인율뱃지":         (None,                            55, 860, None, 0),
    "서브텍스트강조":     (None,                            55, 860, None, 0),
    "믹스 텍스트강조":    ((PAD, PAD, 370, CANVAS_H - PAD), 410, 560, None, 0),
    "믹스 할인율뱃지":    ((PAD, PAD, 370, CANVAS_H - PAD), 410, 560, None, 0),
    "로고 가운데+텍스트": ((310, 25, 700, CANVAS_H - 25),   55, 235, 720, 200),
    "로고 가운데+뱃지":   ((310, 25, 700, CANVAS_H - 25),   55, 235, 720, 200),
    "로고 우측+텍스트":   ((620, PAD, 980, CANVAS_H - PAD), 55, 530, None, 0),
    "로고 우측+뱃지":     ((620, PAD, 980, CANVAS_H - PAD), 55, 530, None, 0),
}

def _fmt_key(fmt: str) -> str:
    return (fmt
        .replace("[믹스] ", "믹스 ")
        .replace("[로고] ", "로고 ")
        .replace("+", "+"))


# ── main entry ────────────────────────────────────────────────────────────────

def generate_png(creative: dict, logo_bytes: bytes) -> bytes:
    """
    creative keys:
      format, main_copy, sub_copy, emphasis_text, emphasis_color,
      emphasis_type ("text"|"badge"|"none"),
      product_images: list[bytes], emoji_images: list[bytes]
    """
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    draw   = ImageDraw.Draw(canvas)

    fmt          = creative.get("format", "텍스트강조")
    main_copy    = creative.get("main_copy", "")
    sub_copy     = creative.get("sub_copy", "")
    emphasis_text = creative.get("emphasis_text", "")
    emphasis_color = creative.get("emphasis_color", "#CC0000")
    emphasis_type  = creative.get("emphasis_type", "none")
    product_images = creative.get("product_images", [])
    emoji_images   = creative.get("emoji_images", [])

    key = _fmt_key(fmt)
    obj_box, text_x, _lw, right_x, _rw = ZONES.get(key, ZONES["텍스트강조"])
    sub_right = creative.get("sub_right", "")

    # 1. Product / logo object
    if obj_box and product_images:
        _paste(canvas, product_images[0], obj_box)

    # 2. Additional product images for 카테고리/믹스 배치
    if obj_box and len(product_images) > 1:
        bw = obj_box[2] - obj_box[0]
        sub_w = bw // len(product_images)
        for i, img_b in enumerate(product_images[1:3], 1):
            sub_box = (
                obj_box[0] + sub_w * i, obj_box[1],
                obj_box[0] + sub_w * (i + 1), obj_box[3],
            )
            _paste(canvas, img_b, sub_box)

    # 3. Emoji (top-right of object zone or near text)
    if emoji_images and obj_box:
        em_size = 56
        em_x = obj_box[2] - em_size - 5
        em_y = obj_box[1] + 5
        for eb in emoji_images[:2]:
            try:
                em = Image.open(io.BytesIO(eb)).convert("RGBA").resize(
                    (em_size, em_size), Image.LANCZOS
                )
                canvas.paste(em, (em_x, em_y), em.split()[3])
                em_x -= em_size + 4
            except Exception:
                pass

    # 4. Text block
    if key in CENTER_FMTS:
        # LEFT: 메인카피(좌) only
        if main_copy:
            _draw_text_block(draw, text_x, CANVAS_H // 2, main_copy, "")
        # RIGHT: 메인카피(우) + 서브카피, with emphasis
        if right_x and (sub_copy or sub_right):
            _draw_text_block(
                draw, right_x, CANVAS_H // 2,
                sub_copy, sub_right,
                emphasis_text, emphasis_color, emphasis_type,
            )
    else:
        if main_copy or sub_copy:
            _draw_text_block(
                draw, text_x, CANVAS_H // 2,
                main_copy, sub_copy,
                emphasis_text, emphasis_color, emphasis_type,
            )

    # 5. ABLY logo (always, top-right)
    if logo_bytes:
        _paste_logo(canvas, logo_bytes)

    buf = io.BytesIO()
    canvas.save(buf, "PNG")
    return buf.getvalue()
