"""ABLY 비즈보드 소재 제작기 — Streamlit Cloud"""
from __future__ import annotations
import io, uuid, zipfile, copy

import streamlit as st
from core.generator import generate_png
from core.removebg import remove_background
from core.emoji import (
    fetch_emoji_candidates, pick_emoji_with_claude,
    fetch_emoji_png, recommend_color_with_claude,
)

st.set_page_config(page_title="ABLY 비즈보드 소재 제작기", page_icon="🗂️", layout="centered")

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* 전체 배경 */
[data-testid="stAppViewContainer"] { background: #F2F2F2; }
[data-testid="stMainBlockContainer"] { max-width: 820px; padding: 0 16px 40px; }

/* 헤더 */
.topbar {
    background: white; border-radius: 12px; padding: 12px 18px;
    display: flex; align-items: center; gap: 10px;
    margin-bottom: 16px; border: 1.5px solid #E8E8E8;
    box-shadow: 0 1px 4px rgba(0,0,0,.05);
}
.topbar-title { font-size: 15px; font-weight: 800; color: #1a1a1a; }
.ably-badge {
    background: #FFDE00; padding: 2px 9px; border-radius: 5px;
    font-size: 13px; font-weight: 800; color: #1a1a1a;
}

/* 카드 */
.s-card {
    background: white; border-radius: 12px; border: 1.5px solid #E8E8E8;
    padding: 16px 18px; margin-bottom: 12px;
}
.s-card-title {
    font-size: 12px; font-weight: 700; color: #3A1D96;
    text-transform: uppercase; letter-spacing: .05em; margin-bottom: 12px;
}
.s-divider { border: none; border-top: 1px solid #EEEEEE; margin: 12px 0; }

/* 포맷 그룹 */
.fmt-groups { display: flex; flex-direction: column; gap: 7px; }
.fmt-group  { display: flex; align-items: center; gap: 8px; }
.fmt-glabel {
    font-size: 10px; font-weight: 700; color: #AAA;
    text-transform: uppercase; letter-spacing: .05em;
    white-space: nowrap; min-width: 32px;
}
.fmt-row { display: flex; flex-wrap: wrap; gap: 5px; }
.fmt-pill {
    border: 1.5px solid #E0E0E0; border-radius: 20px;
    padding: 5px 13px; font-size: 12px; color: #555; font-weight: 500;
    background: white; cursor: pointer; white-space: nowrap;
    transition: all .1s;
}
.fmt-pill:hover  { border-color: #9B76E8; color: #3A1D96; }
.fmt-pill.active { border-color: #3A1D96; background: #3A1D96; color: white; font-weight: 700; }

/* Streamlit 버튼 → pill */
div[data-testid="column"] button {
    border-radius: 20px !important;
    padding: 4px 13px !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    border: 1.5px solid #E0E0E0 !important;
    background: white !important;
    color: #555 !important;
    white-space: nowrap !important;
    min-height: 0 !important;
    height: auto !important;
    line-height: 1.4 !important;
}
div[data-testid="column"] button:hover {
    border-color: #9B76E8 !important; color: #3A1D96 !important;
}
div[data-testid="column"] button[kind="primary"] {
    background: #3A1D96 !important; border-color: #3A1D96 !important;
    color: white !important; font-weight: 700 !important;
}

/* 강조 영역 */
.em-box {
    background: #FFFBF0; border: 1.5px dashed #FFD080;
    border-radius: 8px; padding: 10px 14px; margin-top: 6px;
}
.em-label { font-size: 11px; color: #B45309; font-weight: 600; margin-bottom: 6px; }

/* 투명 안내 */
.transp-note { font-size: 11px; color: #AAA; }

/* 입력 필드 */
div[data-testid="stTextInput"] input { font-size: 13px !important; }
div[data-testid="stTextInput"] label { font-size: 11px !important; color: #777 !important; }

/* expander */
details summary { font-size: 13px !important; font-weight: 600 !important; }

/* 구분선 얇게 */
hr { margin: 10px 0 !important; }
</style>
""", unsafe_allow_html=True)


# ── 에셋 & 시크릿 ──────────────────────────────────────────────────────────────
@st.cache_resource
def _logo() -> bytes:
    with open("assets/logo.png", "rb") as f: return f.read()

def _secret(k: str) -> str:
    try: return st.secrets[k]
    except: return ""

REMOVEBG_KEY  = _secret("REMOVEBG_API_KEY")
ANTHROPIC_KEY = _secret("ANTHROPIC_API_KEY")

# ── 포맷 정의 ──────────────────────────────────────────────────────────────────
FORMATS = {
    "기본": ["가운데 오브젝트", "텍스트강조", "할인율뱃지", "서브텍스트강조"],
    "믹스": ["[믹스] 텍스트강조", "[믹스] 할인율뱃지"],
    "로고": ["[로고] 가운데+텍스트", "[로고] 가운데+뱃지", "[로고] 우측+텍스트", "[로고] 우측+뱃지"],
}
EMPHASIS_TYPE = {
    "텍스트강조": "text", "서브텍스트강조": "text",
    "[믹스] 텍스트강조": "text", "[로고] 가운데+텍스트": "text", "[로고] 우측+텍스트": "text",
    "할인율뱃지": "badge", "[믹스] 할인율뱃지": "badge",
    "[로고] 가운데+뱃지": "badge", "[로고] 우측+뱃지": "badge",
}
HAS_EMPHASIS = set(EMPHASIS_TYPE.keys())
EMPHASIS_Q = {
    "text":  "서브카피 중 어떤 텍스트를 강조할까요?",
    "badge": "서브카피 중 어떤 텍스트에 뱃지를 달아드릴까요?",
}


# ── 세션 초기화 ────────────────────────────────────────────────────────────────
def _new() -> dict:
    return dict(
        id=str(uuid.uuid4())[:8], name="", format="가운데 오브젝트",
        main_copy="", sub_copy="", emphasis_text="",
        emphasis_color="#CC0000", use_recommend=True,
        product_images=[], reference_image=None,
        object_type="단독", use_emoji=False, emoji_keywords="",
        result_png=None,
    )

if "page_name"  not in st.session_state: st.session_state.page_name  = ""
if "creatives"  not in st.session_state: st.session_state.creatives  = [_new()]


# ── 헤더 ────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="topbar">
  <span class="ably-badge">ABLY</span>
  <span class="topbar-title">비즈보드 소재 제작기</span>
</div>
""", unsafe_allow_html=True)

# 피그마 페이지명
st.session_state.page_name = st.text_input(
    "📁 피그마 페이지명", value=st.session_state.page_name,
    placeholder="예시 ) 260611_에이블리_비즈보드_클로드",
    label_visibility="visible",
)


# ── 포맷 선택 위젯 ──────────────────────────────────────────────────────────────
def _fmt_selector(cid: str, current: str) -> str:
    selected = current
    for group, fmts in FORMATS.items():
        short_labels = [f.replace("[믹스] ", "").replace("[로고] ", "") for f in fmts]
        # 그룹 레이블 + 버튼을 한 줄에
        g_col, *btn_cols = st.columns([0.7] + [1.8] * len(fmts))
        g_col.markdown(
            f"<div style='font-size:10px;font-weight:700;color:#AAA;"
            f"text-transform:uppercase;padding-top:7px'>{group}</div>",
            unsafe_allow_html=True,
        )
        for col, fmt, lbl in zip(btn_cols, fmts, short_labels):
            if col.button(lbl, key=f"fmt_{cid}_{fmt}",
                          type="primary" if fmt == selected else "secondary",
                          use_container_width=True):
                selected = fmt
    return selected


# ── 소재 카드 ──────────────────────────────────────────────────────────────────
def _card(idx: int, c: dict):
    cid   = c["id"]
    title = c["name"] or f"소재 {idx+1}"
    tag   = c["format"]

    with st.expander(f"**{idx+1}.** {title}　`{tag}`", expanded=True):

        # 소재명 + 포맷 선택
        c["name"] = st.text_input("소재명", value=c["name"],
                                   placeholder="예: 헬로키티_믹스뱃지",
                                   key=f"name_{cid}")

        st.markdown("<div class='s-card-title'>포맷 선택</div>", unsafe_allow_html=True)
        c["format"] = _fmt_selector(cid, c["format"])
        fmt     = c["format"]
        em_type = EMPHASIS_TYPE.get(fmt, "none")

        st.markdown("<hr class='s-divider'>", unsafe_allow_html=True)

        # ── 카피 ──
        st.markdown("<div class='s-card-title'>카피</div>", unsafe_allow_html=True)
        c["main_copy"] = st.text_input(
            "메인카피 · Bold · #4C4C4C", value=c["main_copy"],
            placeholder="예: [헬로키티 크록스] 쫀득 말랑 착화감",
            key=f"main_{cid}")
        c["sub_copy"] = st.text_input(
            "서브카피 · Regular · #777777", value=c["sub_copy"],
            placeholder="예: 무료배송 + SALE",
            key=f"sub_{cid}")

        # 강조 / 뱃지
        if fmt in HAS_EMPHASIS:
            st.markdown(
                f"<div class='em-box'>"
                f"<div class='em-label'>{EMPHASIS_Q[em_type]}</div></div>",
                unsafe_allow_html=True)
            c["emphasis_text"] = st.text_input(
                "강조 텍스트", value=c["emphasis_text"],
                placeholder="예: 무료배송 / 75%",
                key=f"em_{cid}")
            col_rec, col_clr = st.columns([1, 1])
            c["use_recommend"] = col_rec.checkbox(
                "색상 AI 추천", value=c.get("use_recommend", True), key=f"rec_{cid}")
            if not c["use_recommend"]:
                c["emphasis_color"] = col_clr.color_picker(
                    "강조 색상", value=c.get("emphasis_color", "#CC0000"), key=f"clr_{cid}")

        st.markdown("<hr class='s-divider'>", unsafe_allow_html=True)

        # ── 오브젝트 이미지 ──
        st.markdown("<div class='s-card-title'>오브젝트 이미지</div>", unsafe_allow_html=True)
        col_ref, col_prod = st.columns(2)

        with col_ref:
            st.caption("레퍼런스 (선택)")
            ref = st.file_uploader("레퍼런스", type=["png","jpg","jpeg","webp"],
                                   key=f"ref_{cid}", label_visibility="collapsed")
            if ref:
                c["reference_image"] = ref.read()
                st.image(c["reference_image"], use_container_width=True)

        with col_prod:
            st.caption("상품 이미지 ✱ (1~3장)")
            prods = st.file_uploader("상품 이미지", type=["png","jpg","jpeg","webp"],
                                     accept_multiple_files=True, key=f"prod_{cid}",
                                     label_visibility="collapsed")
            if prods:
                raws = [f.read() for f in prods[:3]]
                if REMOVEBG_KEY:
                    with st.spinner("배경 제거 중…"):
                        c["product_images"] = [remove_background(b, REMOVEBG_KEY) for b in raws]
                else:
                    c["product_images"] = raws
                for b in c["product_images"]:
                    st.image(b, use_container_width=True)

        c["object_type"] = st.radio(
            "배치 타입", ["단독","카테고리","믹스(코디)"], horizontal=True,
            index=["단독","카테고리","믹스(코디)"].index(c.get("object_type","단독")),
            key=f"otype_{cid}")

        st.markdown("<hr class='s-divider'>", unsafe_allow_html=True)

        # ── 이모티콘 ──
        c["use_emoji"] = st.toggle("이모티콘 추가", value=c.get("use_emoji", False), key=f"emoji_{cid}")
        if c["use_emoji"]:
            c["emoji_keywords"] = st.text_input(
                "이모티콘 키워드", value=c.get("emoji_keywords",""),
                placeholder="예: 여름, 하트 · 공란이면 광고 뉘앙스로 자동 선택",
                key=f"ekw_{cid}")

        st.markdown("<hr class='s-divider'>", unsafe_allow_html=True)
        st.markdown("<div class='transp-note'>ℹ️ 배경 없는 투명 PNG로 저장됩니다</div>",
                    unsafe_allow_html=True)
        st.write("")

        # 삭제 / 복제
        bc1, bc2, _ = st.columns([1, 1, 4])
        if bc1.button("🗑 삭제", key=f"del_{cid}"):
            st.session_state.creatives = [x for x in st.session_state.creatives if x["id"] != cid]
            st.rerun()
        if bc2.button("📋 복제", key=f"dup_{cid}"):
            nc = copy.deepcopy(c); nc["id"] = str(uuid.uuid4())[:8]
            nc["name"] = c["name"]+"_복사"; nc["result_png"] = None
            i = next(i for i,x in enumerate(st.session_state.creatives) if x["id"]==cid)
            st.session_state.creatives.insert(i+1, nc)
            st.rerun()

        # 결과 미리보기
        if c.get("result_png"):
            st.image(c["result_png"], use_container_width=True)
            st.download_button(
                f"⬇ PNG 다운로드 — {c['name'] or f'소재{idx+1}'}",
                data=c["result_png"],
                file_name=f"{c['name'] or f'creative_{idx+1}'}.png",
                mime="image/png", key=f"dl_{cid}")


# ── 렌더 ──────────────────────────────────────────────────────────────────────
for i, c in enumerate(st.session_state.creatives):
    _card(i, c)

if st.button("＋ 소재 추가", use_container_width=True):
    st.session_state.creatives.append(_new()); st.rerun()

st.write("")

# ── 전체 생성 버튼 ─────────────────────────────────────────────────────────────
if st.button("▶ 전체 소재 생성", type="primary", use_container_width=True):
    logo = _logo()
    with st.spinner("소재 생성 중…"):
        for c in st.session_state.creatives:
            try:
                if c.get("use_recommend") and ANTHROPIC_KEY and c["format"] in HAS_EMPHASIS:
                    c["emphasis_color"] = recommend_color_with_claude(
                        c["main_copy"], c["sub_copy"], ANTHROPIC_KEY)
                emoji_images = []
                if c.get("use_emoji"):
                    kw = c.get("emoji_keywords","") or c["main_copy"]+" "+c["sub_copy"]
                    cands = fetch_emoji_candidates(kw)
                    chosen = pick_emoji_with_claude(cands, c["main_copy"], c["sub_copy"], ANTHROPIC_KEY)
                    emoji_images = [b for e in chosen if (b := fetch_emoji_png(e.get("img_url","")))]
                c["result_png"] = generate_png({
                    "format": c["format"], "main_copy": c["main_copy"],
                    "sub_copy": c["sub_copy"], "emphasis_text": c["emphasis_text"],
                    "emphasis_color": c["emphasis_color"],
                    "emphasis_type": EMPHASIS_TYPE.get(c["format"], "none"),
                    "product_images": c["product_images"], "emoji_images": emoji_images,
                }, logo)
            except Exception as e:
                st.error(f"{c['name'] or c['id']}: {e}")
    st.success(f"✅ {len(st.session_state.creatives)}개 완료!")
    st.rerun()

# ── ZIP 다운로드 ───────────────────────────────────────────────────────────────
done = [c for c in st.session_state.creatives if c.get("result_png")]
if done:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        pg = st.session_state.page_name or "bizboard"
        for i, c in enumerate(done):
            zf.writestr(f"{pg}_{c['name'] or f'creative_{i+1}'}.png", c["result_png"])
    buf.seek(0)
    st.download_button(
        f"⬇ 전체 ZIP ({len(done)}개)", data=buf,
        file_name=f"{st.session_state.page_name or 'bizboard'}.zip",
        mime="application/zip", use_container_width=True)
