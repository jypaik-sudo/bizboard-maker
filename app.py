"""카카오 비즈보드 소재 제작기 — Streamlit Cloud"""
from __future__ import annotations
import io
import uuid
import zipfile

import streamlit as st
from PIL import Image

from core.generator import generate_png
from core.removebg import remove_background
from core.emoji import (
    fetch_emoji_candidates,
    pick_emoji_with_claude,
    fetch_emoji_png,
    recommend_color_with_claude,
)

# ── 페이지 설정 ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="ABLY 비즈보드 소재 제작기", page_icon="🗂️", layout="wide")

# ── 공통 CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* 포맷 버튼 pill 스타일 */
div[data-testid="column"] button[kind="secondary"] {
    border-radius: 20px !important;
    padding: 4px 14px !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    border: 1.5px solid #E8E8E8 !important;
    white-space: nowrap !important;
}
/* 선택된 포맷 버튼 */
div[data-testid="column"] button[kind="primary"] {
    border-radius: 20px !important;
    padding: 4px 14px !important;
    font-size: 12px !important;
    font-weight: 700 !important;
    white-space: nowrap !important;
}
/* 소재 카드 구분선 */
div[data-testid="stExpander"] { border-radius: 12px !important; }
/* 미리보기 이미지 테두리 */
img { border-radius: 6px; }
</style>
""", unsafe_allow_html=True)


# ── 에셋 로드 ─────────────────────────────────────────────────────────────────
@st.cache_resource
def _logo_bytes() -> bytes:
    with open("assets/logo.png", "rb") as f:
        return f.read()


# ── API 키 (Streamlit Secrets) ────────────────────────────────────────────────
def _secret(key: str) -> str:
    try:
        return st.secrets[key]
    except Exception:
        return ""

REMOVEBG_KEY  = _secret("REMOVEBG_API_KEY")
ANTHROPIC_KEY = _secret("ANTHROPIC_API_KEY")


# ── 포맷 정의 ─────────────────────────────────────────────────────────────────
FORMATS = {
    "기본": ["가운데 오브젝트", "텍스트강조", "할인율뱃지", "서브텍스트강조"],
    "믹스": ["[믹스] 텍스트강조", "[믹스] 할인율뱃지"],
    "로고": ["[로고] 가운데+텍스트", "[로고] 가운데+뱃지", "[로고] 우측+텍스트", "[로고] 우측+뱃지"],
}

# 포맷별 강조 타입
EMPHASIS_TYPE = {
    "텍스트강조":           "text",
    "서브텍스트강조":       "text",
    "[믹스] 텍스트강조":    "text",
    "[로고] 가운데+텍스트": "text",
    "[로고] 우측+텍스트":   "text",
    "할인율뱃지":           "badge",
    "[믹스] 할인율뱃지":    "badge",
    "[로고] 가운데+뱃지":   "badge",
    "[로고] 우측+뱃지":     "badge",
}
HAS_EMPHASIS = set(EMPHASIS_TYPE.keys())

# 강조/뱃지 질문 텍스트
EMPHASIS_Q = {
    "text":  "서브카피 중 어떤 텍스트를 강조할까요?",
    "badge": "서브카피 중 어떤 텍스트에 뱃지를 달아드릴까요?",
}


# ── Session State 초기화 ──────────────────────────────────────────────────────
if "page_name" not in st.session_state:
    st.session_state.page_name = ""
if "creatives" not in st.session_state:
    st.session_state.creatives = [_new_creative()]


def _new_creative() -> dict:
    return {
        "id":             str(uuid.uuid4())[:8],
        "name":           "",
        "format":         "가운데 오브젝트",
        "main_copy":      "",
        "sub_copy":       "",
        "emphasis_text":  "",
        "emphasis_color": "#CC0000",
        "use_recommend":  True,
        "product_images": [],   # list[bytes]
        "reference_image": None,
        "object_type":    "단독",
        "use_emoji":      False,
        "emoji_keywords": "",
        "result_png":     None,
    }


# ── 헤더 ─────────────────────────────────────────────────────────────────────
col_logo, col_title = st.columns([1, 8])
with col_logo:
    st.image("assets/logo.png", width=80)
with col_title:
    st.markdown("## ABLY 비즈보드 소재 제작기")
    st.caption("카카오 비즈보드 1029×258px · 투명 PNG · 심사 규정 준수")

st.divider()

# ── 피그마 페이지명 ────────────────────────────────────────────────────────────
st.session_state.page_name = st.text_input(
    "📁 피그마 페이지명",
    value=st.session_state.page_name,
    placeholder="예시 ) 260611_에이블리_비즈보드_클로드",
    help="이 이름으로 피그마에 새 페이지가 생성됩니다",
)
st.divider()


# ── 포맷 선택 위젯 ────────────────────────────────────────────────────────────
def _fmt_selector(cid: str, current_fmt: str) -> str:
    """그룹별 pill 버튼. 선택된 포맷 반환."""
    selected = current_fmt
    for group_name, fmts in FORMATS.items():
        cols = st.columns([1] + [2] * len(fmts))
        cols[0].markdown(
            f"<div style='font-size:10px;font-weight:700;color:#AAA;"
            f"text-transform:uppercase;letter-spacing:.05em;"
            f"padding-top:8px'>{group_name}</div>",
            unsafe_allow_html=True,
        )
        for i, fmt in enumerate(fmts):
            label = fmt.replace("[믹스] ", "").replace("[로고] ", "")
            is_active = fmt == selected
            if cols[i + 1].button(
                label,
                key=f"fmt_{cid}_{fmt}",
                type="primary" if is_active else "secondary",
                use_container_width=True,
            ):
                selected = fmt
    return selected


# ── 소재 카드 렌더 ─────────────────────────────────────────────────────────────
def _render_creative(idx: int, c: dict) -> None:
    cid   = c["id"]
    label = c["name"] or f"소재 {idx + 1}"

    with st.expander(f"**{idx+1}. {label}**　`{c['format']}`", expanded=True):

        # 소재명
        c["name"] = st.text_input("소재명", value=c["name"],
                                   placeholder="예: 헬로키티_믹스뱃지",
                                   key=f"name_{cid}")

        # ── 포맷 선택 ──
        st.markdown("**포맷 선택**")
        c["format"] = _fmt_selector(cid, c["format"])
        fmt = c["format"]
        em_type = EMPHASIS_TYPE.get(fmt, "none")

        st.divider()

        # ── 카피 ──
        st.markdown(f"**카피** — `{fmt}`")

        c["main_copy"] = st.text_input(
            "메인카피 · Bold · #4C4C4C",
            value=c["main_copy"],
            placeholder="예: [헬로키티 크록스] 쫀득 말랑 착화감",
            key=f"main_{cid}",
        )
        c["sub_copy"] = st.text_input(
            "서브카피 · Regular · #777777",
            value=c["sub_copy"],
            placeholder="예: 무료배송 + SALE",
            key=f"sub_{cid}",
        )

        # 강조 / 뱃지 영역
        if fmt in HAS_EMPHASIS:
            with st.container():
                st.markdown(
                    f"<div style='background:#FFFBF0;border:1.5px dashed #FFD080;"
                    f"border-radius:8px;padding:12px 14px;margin-top:8px'>"
                    f"<span style='font-size:12px;color:#B45309;font-weight:600'>"
                    f"↳ {EMPHASIS_Q[em_type]}</span></div>",
                    unsafe_allow_html=True,
                )

                c["emphasis_text"] = st.text_input(
                    "강조 텍스트",
                    value=c["emphasis_text"],
                    placeholder="예: 무료배송 / 75%",
                    key=f"em_text_{cid}",
                )

                col_rec, col_color = st.columns([2, 3])
                c["use_recommend"] = col_rec.checkbox(
                    "색상 AI 추천",
                    value=c.get("use_recommend", True),
                    key=f"rec_{cid}",
                    help="오브젝트/로고 컬러에 맞춰 Claude가 자동 선택합니다",
                )
                if not c["use_recommend"]:
                    c["emphasis_color"] = col_color.color_picker(
                        "강조 색상",
                        value=c.get("emphasis_color", "#CC0000"),
                        key=f"em_color_{cid}",
                    )

        st.divider()

        # ── 오브젝트 이미지 ──
        st.markdown("**오브젝트 이미지**")

        col_ref, col_prod = st.columns(2)
        with col_ref:
            st.caption("레퍼런스 (배치 참고)")
            ref_file = st.file_uploader(
                "참고 예시", type=["png", "jpg", "jpeg", "webp"],
                key=f"ref_{cid}", label_visibility="collapsed",
            )
            if ref_file:
                c["reference_image"] = ref_file.read()
                st.image(c["reference_image"], use_container_width=True)

        with col_prod:
            st.caption("상품 이미지 ✱ (1~3장)")
            prod_files = st.file_uploader(
                "상품 스크린샷", type=["png", "jpg", "jpeg", "webp"],
                accept_multiple_files=True, key=f"prod_{cid}",
                label_visibility="collapsed",
            )
            if prod_files:
                raw_imgs = [f.read() for f in prod_files[:3]]
                if REMOVEBG_KEY:
                    with st.spinner("배경 제거 중…"):
                        c["product_images"] = [
                            remove_background(b, REMOVEBG_KEY) for b in raw_imgs
                        ]
                else:
                    c["product_images"] = raw_imgs
                for b in c["product_images"]:
                    st.image(b, use_container_width=True)

        # 배치 타입
        c["object_type"] = st.radio(
            "배치 타입",
            ["단독", "카테고리", "믹스(코디)"],
            horizontal=True,
            index=["단독", "카테고리", "믹스(코디)"].index(c.get("object_type", "단독")),
            key=f"obj_type_{cid}",
        )

        st.divider()

        # ── 이모티콘 ──
        c["use_emoji"] = st.toggle("이모티콘 추가", value=c.get("use_emoji", False), key=f"emoji_{cid}")
        if c["use_emoji"]:
            c["emoji_keywords"] = st.text_input(
                "키워드",
                value=c.get("emoji_keywords", ""),
                placeholder="예: 여름, 하트 · 공란이면 광고 뉘앙스로 자동 선택",
                key=f"emoji_kw_{cid}",
            )

        st.divider()

        # ── 삭제 / 복제 ──
        col_del, col_dup, _ = st.columns([1, 1, 4])
        if col_del.button("🗑 삭제", key=f"del_{cid}"):
            st.session_state.creatives = [
                x for x in st.session_state.creatives if x["id"] != cid
            ]
            st.rerun()
        if col_dup.button("📋 복제", key=f"dup_{cid}"):
            import copy
            new_c = copy.deepcopy(c)
            new_c["id"] = str(uuid.uuid4())[:8]
            new_c["name"] = c["name"] + "_복사"
            new_c["result_png"] = None
            idx_now = next(
                i for i, x in enumerate(st.session_state.creatives) if x["id"] == cid
            )
            st.session_state.creatives.insert(idx_now + 1, new_c)
            st.rerun()

        # ── 결과 미리보기 ──
        if c.get("result_png"):
            st.markdown("**생성 결과**")
            st.image(c["result_png"], use_container_width=True)
            st.download_button(
                f"⬇ PNG 다운로드 — {c['name'] or f'소재{idx+1}'}",
                data=c["result_png"],
                file_name=f"{c['name'] or f'creative_{idx+1}'}.png",
                mime="image/png",
                key=f"dl_{cid}",
            )


# ── 소재 목록 렌더 ────────────────────────────────────────────────────────────
for i, c in enumerate(st.session_state.creatives):
    _render_creative(i, c)

if st.button("＋ 소재 추가", use_container_width=True):
    st.session_state.creatives.append(_new_creative())
    st.rerun()

st.divider()


# ── 전체 생성 ─────────────────────────────────────────────────────────────────
if st.button("▶ 전체 소재 생성", type="primary", use_container_width=True):
    logo = _logo_bytes()
    errors = []

    with st.spinner("소재 생성 중…"):
        for c in st.session_state.creatives:
            try:
                # AI 색상 추천
                if c.get("use_recommend") and ANTHROPIC_KEY and c["format"] in HAS_EMPHASIS:
                    c["emphasis_color"] = recommend_color_with_claude(
                        c["main_copy"], c["sub_copy"], ANTHROPIC_KEY
                    )

                # 이모티콘
                emoji_images: list[bytes] = []
                if c.get("use_emoji"):
                    kw = c.get("emoji_keywords", "") or (c["main_copy"] + " " + c["sub_copy"])
                    candidates = fetch_emoji_candidates(kw)
                    if ANTHROPIC_KEY:
                        chosen = pick_emoji_with_claude(
                            candidates, c["main_copy"], c["sub_copy"], ANTHROPIC_KEY
                        )
                    else:
                        chosen = candidates[:2]
                    emoji_images = [b for e in chosen if (b := fetch_emoji_png(e.get("img_url", "")))]

                creative_data = {
                    "format":         c["format"],
                    "main_copy":      c["main_copy"],
                    "sub_copy":       c["sub_copy"],
                    "emphasis_text":  c["emphasis_text"],
                    "emphasis_color": c["emphasis_color"],
                    "emphasis_type":  EMPHASIS_TYPE.get(c["format"], "none"),
                    "product_images": c["product_images"],
                    "emoji_images":   emoji_images,
                }
                c["result_png"] = generate_png(creative_data, logo)

            except Exception as e:
                errors.append(f"{c['name'] or c['id']}: {e}")

    if errors:
        st.error("\n".join(errors))
    else:
        st.success(f"✅ {len(st.session_state.creatives)}개 소재 생성 완료!")

    st.rerun()


# ── 전체 ZIP 다운로드 ─────────────────────────────────────────────────────────
done = [c for c in st.session_state.creatives if c.get("result_png")]
if done:
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        page = st.session_state.page_name or "bizboard"
        for i, c in enumerate(done):
            fname = f"{page}_{c['name'] or f'creative_{i+1}'}.png"
            zf.writestr(fname, c["result_png"])
    zip_buf.seek(0)

    st.download_button(
        f"⬇ 전체 ZIP 다운로드 ({len(done)}개)",
        data=zip_buf,
        file_name=f"{st.session_state.page_name or 'bizboard'}.zip",
        mime="application/zip",
        use_container_width=True,
    )
    st.caption("ℹ️ 배경 없는 투명 PNG · 카카오 비즈보드 등록용")
